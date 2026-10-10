"""Pydantic request/response models (the public API contract)."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.utils.text_normalization import split_list_input

SCORE_DISCLAIMER = (
    "Scores estimate how closely a resume matches the job description. They are not probabilities of "
    "hiring success and must not be used to accept or reject candidates automatically."
)


# ---------- requests ----------
class JobRequirements(BaseModel):
    job_title: str = Field(max_length=200)
    job_description: str
    required_skills: list[str] = Field(default_factory=list, max_length=50)
    preferred_skills: list[str] = Field(default_factory=list, max_length=50)
    min_experience_years: Optional[float] = Field(default=None, ge=0, le=60)
    education_requirement: Optional[str] = Field(default=None, max_length=300)

    @field_validator("job_title")
    @classmethod
    def _title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Job title is required.")
        return v

    @field_validator("job_description")
    @classmethod
    def _description(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Job description is required.")
        return v

    @field_validator("required_skills", "preferred_skills", mode="before")
    @classmethod
    def _skills(cls, v):
        items = split_list_input(v)
        for item in items:
            if len(item) > 80:
                raise ValueError("Each skill must be 80 characters or fewer.")
        return items

    @field_validator("min_experience_years", mode="before")
    @classmethod
    def _years(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v

    @field_validator("education_requirement", mode="before")
    @classmethod
    def _education(cls, v):
        if v is None:
            return None
        v = str(v).strip()
        return v or None


# ---------- response parts ----------
class JobInfo(BaseModel):
    job_title: str
    description_characters: int
    required_skills: list[str]
    preferred_skills: list[str]
    min_experience_years: Optional[float] = None
    education_requirement: Optional[str] = None


class ScoreComponent(BaseModel):
    key: Literal["required_skills", "preferred_skills", "semantic_similarity"]
    label: str
    score: Optional[float] = Field(description="Component score 0-100; null when not applicable.")
    configured_weight: float = Field(description="Weight from configuration (fraction).")
    effective_weight: float = Field(description="Weight actually used after redistribution (fraction).")
    contribution: float = Field(description="Points this component adds to the final 0-100 score.")
    available: bool
    detail: str


class ScoreBreakdown(BaseModel):
    final_score: float = Field(ge=0, le=100)
    components: list[ScoreComponent]
    notes: list[str] = Field(default_factory=list)
    scoring_version: str


class EvidenceSnippet(BaseModel):
    skill: str
    snippet: str
    line: int = Field(description="1-based line number in the extracted resume text.")


class ExperienceMention(BaseModel):
    years: float
    snippet: str
    line: int


class ExperienceInfo(BaseModel):
    required_years: Optional[float] = None
    status: Literal["not_requested", "mentions_found", "no_explicit_mention"]
    max_stated_years: Optional[float] = None
    mentions: list[ExperienceMention] = Field(default_factory=list)
    note: str


class CandidateResult(BaseModel):
    resume_id: str
    rank: int
    upload_index: int
    filename: str
    status: Literal["processed"] = "processed"
    score: float = Field(ge=0, le=100, description="Composite matching score, 0-100.")
    semantic_score: float = Field(ge=0, le=100, description="Normalised semantic similarity, 0-100.")
    semantic_cosine: float = Field(description="Raw cosine similarity from the embedding model.")
    required_matched: list[str]
    required_not_found: list[str]
    preferred_matched: list[str]
    preferred_not_found: list[str]
    extracted_skills: list[str]
    score_breakdown: ScoreBreakdown
    evidence: list[EvidenceSnippet] = Field(default_factory=list)
    experience: ExperienceInfo
    warnings: list[str] = Field(default_factory=list)
    extracted_characters: int
    model_id: str


class FileError(BaseModel):
    upload_index: int
    filename: str
    status: Literal["failed"] = "failed"
    code: str
    message: str


class ProcessingSummary(BaseModel):
    total_uploaded: int
    processed: int
    failed: int
    candidates_with_results: int
    average_score: Optional[float] = None


class MatchResponse(BaseModel):
    request_id: str
    generated_at: str
    job: JobInfo
    model_id: str
    scoring_version: str
    skill_dictionary_version: str
    summary: ProcessingSummary
    candidates: list[CandidateResult]
    errors: list[FileError]
    score_disclaimer: str = SCORE_DISCLAIMER


class ExportRequest(BaseModel):
    candidates: list[CandidateResult] = Field(default_factory=list, max_length=500)
    errors: list[FileError] = Field(default_factory=list, max_length=500)


# ---------- meta ----------
class ModelStatus(BaseModel):
    status: Literal["not_loaded", "loading", "ready", "failed"]
    model_id: str
    error_code: Optional[str] = None


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    live: bool = True
    ready: bool
    model: ModelStatus
    version: str
    api_version: str


class ModelInfoResponse(BaseModel):
    model_id: str
    model_type: str
    ready: bool
    status: str
    scoring_config_version: str
    skill_dictionary_version: str


class ConfigResponse(BaseModel):
    scoring_weights: dict[str, float]
    scoring_config_version: str
    skill_dictionary_version: str
    skill_dictionary_sha256: str
    supported_extensions: list[str]
    max_file_size_mb: float
    max_files_per_request: int
    min_job_description_chars: int
    max_job_description_chars: int


class VersionResponse(BaseModel):
    app_name: str
    version: str
    api_version: str


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
