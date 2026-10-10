from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from app import API_VERSION, __version__
from app.api.deps import ServiceContainer, get_services
from app.schemas import HealthResponse, ModelStatus

router = APIRouter(tags=["health"])


def _build(services: ServiceContainer) -> HealthResponse:
    matcher = services.matcher
    return HealthResponse(
        ready=matcher.is_ready,
        model=ModelStatus(status=matcher.status, model_id=matcher.model_id, error_code=matcher.error_code),
        version=__version__,
        api_version=API_VERSION,
    )


@router.get("/health", response_model=HealthResponse, summary="Liveness plus model readiness")
def health(services: ServiceContainer = Depends(get_services)) -> HealthResponse:
    """Always 200 while the process is alive. ``ready`` says whether predictions can be served."""
    return _build(services)


@router.get("/health/ready", response_model=HealthResponse, summary="Readiness probe")
def ready(response: Response, services: ServiceContainer = Depends(get_services)) -> HealthResponse:
    """200 only when the model is loaded; 503 otherwise."""
    body = _build(services)
    if not body.ready:
        response.status_code = 503
    return body
