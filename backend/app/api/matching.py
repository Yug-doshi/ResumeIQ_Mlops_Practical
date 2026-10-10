from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from app.api.deps import ServiceContainer, get_services
from app.exceptions import AppError, ResumeParseError
from app.schemas import ExportRequest, JobRequirements, MatchResponse
from app.services.matching_service import UploadedResume
from app.utils.csv_export import build_results_csv
from app.utils.file_validation import sanitize_filename

router = APIRouter(prefix="/api/v1", tags=["matching"])

READ_CHUNK = 1024 * 1024


async def _read_limited(upload: UploadFile, max_bytes: int) -> tuple[Optional[bytes], bool]:
    """Read at most ``max_bytes``; report if the file is larger (without keeping the excess)."""
    data = bytearray()
    while True:
        chunk = await upload.read(READ_CHUNK)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > max_bytes:
            return None, True
    return bytes(data), False


def _friendly_validation_message(exc: ValidationError) -> str:
    messages = []
    for err in exc.errors():
        msg = err.get("msg", "Invalid value").removeprefix("Value error, ")
        field = ".".join(str(p) for p in err.get("loc", ()))
        messages.append(msg if msg.endswith(".") and field in {"job_title", "job_description"} else f"{field}: {msg}")
    return " ".join(messages)


@router.post("/match", response_model=MatchResponse, summary="Rank uploaded resumes against a job")
async def match_resumes(
    job_title: str = Form(""),
    job_description: str = Form(""),
    required_skills: str = Form("", description="Comma/newline separated, or a JSON array."),
    preferred_skills: str = Form("", description="Comma/newline separated, or a JSON array."),
    min_experience_years: Optional[str] = Form(None),
    education_requirement: Optional[str] = Form(None),
    resumes: list[UploadFile] = File(default=[]),
    services: ServiceContainer = Depends(get_services),
) -> MatchResponse:
    settings = services.settings
    try:
        job = JobRequirements(
            job_title=job_title,
            job_description=job_description,
            required_skills=required_skills,
            preferred_skills=preferred_skills,
            min_experience_years=min_experience_years,
            education_requirement=education_requirement,
        )
    except ValidationError as exc:
        raise AppError(422, "invalid_job", _friendly_validation_message(exc))

    if len(job.job_description) < settings.min_job_description_chars:
        raise AppError(422, "job_description_too_short",
                       f"The job description must be at least {settings.min_job_description_chars} characters.")
    if len(job.job_description) > settings.max_job_description_chars:
        raise AppError(422, "job_description_too_long",
                       f"The job description must be at most {settings.max_job_description_chars} characters.")
    if not resumes:
        raise AppError(422, "no_files", "Upload at least one resume (PDF or DOCX).")
    if len(resumes) > settings.max_files_per_request:
        raise AppError(422, "too_many_files",
                       f"At most {settings.max_files_per_request} resumes can be analysed per request.")

    uploads: list[UploadedResume] = []
    for index, upload in enumerate(resumes):
        name = sanitize_filename(upload.filename)
        data, too_large = await _read_limited(upload, settings.max_file_size_bytes)
        if too_large:
            uploads.append(UploadedResume(index, name, precheck_error=ResumeParseError(
                "file_too_large", f"The file is larger than the {settings.max_file_size_mb:g} MB limit.")))
        else:
            uploads.append(UploadedResume(index, name, content=data))

    # Fail fast with 503 (never fake scores) if the model cannot be loaded.
    await run_in_threadpool(services.matcher.ensure_loaded)
    return await run_in_threadpool(services.matching_service.run, job, uploads)


@router.post("/export/csv", summary="Build a CSV from results the client already holds")
def export_csv(payload: ExportRequest) -> Response:
    """Stateless: the server stores nothing, so the client sends back the rows it wants exported."""
    body = build_results_csv(payload.candidates, payload.errors)
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="resumeiq_results.csv"'},
    )
