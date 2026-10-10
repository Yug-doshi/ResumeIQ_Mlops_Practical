"""FastAPI application factory."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import API_VERSION, __version__
from app.api import health, matching, model_info
from app.api.deps import ServiceContainer
from app.config import Settings, get_settings, load_scoring_config
from app.exceptions import AppError, ModelUnavailableError
from app.services.matching_service import MatchingService
from app.services.semantic_matcher import SemanticMatcher, SentenceTransformerBackend
from app.services.skill_extractor import SkillExtractor

logger = logging.getLogger("resumeiq")


def _error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def create_app(settings: Optional[Settings] = None, matcher: Optional[SemanticMatcher] = None) -> FastAPI:
    """Build the app. ``matcher`` can be injected (tests, or a future registry-backed loader)."""
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    extractor = SkillExtractor.from_file(settings.skills_config_path)
    scoring_config = load_scoring_config(settings.scoring_config_path)
    if matcher is None:
        matcher = SemanticMatcher(
            SentenceTransformerBackend(
                settings.model_name,
                cache_dir=settings.model_cache_dir,
                local_files_only=settings.model_local_files_only,
            )
        )
    services = ServiceContainer(
        settings=settings,
        extractor=extractor,
        matcher=matcher,
        scoring_config=scoring_config,
        matching_service=MatchingService(settings, extractor, matcher, scoring_config),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if settings.preload_model:
            try:
                matcher.load()  # load once at startup; /match retries if this failed
            except ModelUnavailableError:
                logger.warning("Starting without a ready model; /health reports ready=false.")
        yield

    app = FastAPI(
        title=f"{settings.app_name} API",
        version=__version__,
        description="Resume screening and skill matching. Scores are estimates to assist human reviewers.",
        lifespan=lifespan,
    )
    app.state.services = services

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    @app.middleware("http")
    async def limit_request_size(request: Request, call_next):
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > settings.max_request_bytes:
            return _error(413, "request_too_large", "The upload is too large. Reduce the number or size of files.")
        return await call_next(request)

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError):
        return _error(exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError):
        parts = [f"{'.'.join(str(p) for p in e['loc'] if p != 'body')}: {e['msg']}" for e in exc.errors()]
        return _error(422, "invalid_request", "Invalid request. " + "; ".join(parts))

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(_: Request, exc: StarletteHTTPException):
        return _error(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(Exception)
    async def unhandled_handler(_: Request, exc: Exception):
        logger.exception("Unhandled error")  # stack trace stays in the server log only
        return _error(500, "internal_error", "An unexpected error occurred.")

    app.include_router(health.router)
    app.include_router(model_info.router)
    app.include_router(matching.router)
    return app


app = create_app()
