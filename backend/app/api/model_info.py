from __future__ import annotations

from fastapi import APIRouter, Depends

from app import API_VERSION, __version__
from app.api.deps import ServiceContainer, get_services
from app.schemas import ConfigResponse, ModelInfoResponse, VersionResponse
from app.utils.file_validation import ALLOWED_EXTENSIONS

router = APIRouter(tags=["meta"])


@router.get("/api/v1/model-info", response_model=ModelInfoResponse)
def model_info(services: ServiceContainer = Depends(get_services)) -> ModelInfoResponse:
    return ModelInfoResponse(
        model_id=services.matcher.model_id,
        model_type="Pretrained sentence-embedding model (inference only, no fine-tuning)",
        ready=services.matcher.is_ready,
        status=services.matcher.status,
        scoring_config_version=services.scoring_config.version,
        skill_dictionary_version=services.extractor.dictionary.version,
    )


@router.get("/api/v1/config", response_model=ConfigResponse)
def config(services: ServiceContainer = Depends(get_services)) -> ConfigResponse:
    s = services.settings
    w = services.scoring_config.weights
    return ConfigResponse(
        scoring_weights=w.model_dump(),
        scoring_config_version=services.scoring_config.version,
        skill_dictionary_version=services.extractor.dictionary.version,
        skill_dictionary_sha256=services.extractor.dictionary.sha256,
        supported_extensions=sorted(ALLOWED_EXTENSIONS),
        max_file_size_mb=s.max_file_size_mb,
        max_files_per_request=s.max_files_per_request,
        min_job_description_chars=s.min_job_description_chars,
        max_job_description_chars=s.max_job_description_chars,
    )


@router.get("/api/v1/version", response_model=VersionResponse)
def version(services: ServiceContainer = Depends(get_services)) -> VersionResponse:
    return VersionResponse(app_name=services.settings.app_name, version=__version__, api_version=API_VERSION)
