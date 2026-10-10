"""Application settings and scoring configuration.

Settings come from environment variables / ``.env`` (see ``.env.example``).
Scoring weights live in ``config/scoring.json`` so they can later be versioned
(for example with DVC) and tracked (for example with MLflow) without code changes.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "ResumeIQ"
    environment: str = "development"
    log_level: str = "INFO"

    # Comma-separated list of allowed frontend origins.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Upload limits
    max_file_size_mb: float = 5.0
    max_files_per_request: int = 25
    max_pdf_pages: int = 30
    max_docx_uncompressed_mb: float = 50.0
    max_extracted_chars: int = 200_000
    min_extracted_chars: int = 30

    # Job input limits
    min_job_description_chars: int = 20
    max_job_description_chars: int = 20_000

    # Semantic model
    model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    model_cache_dir: Optional[str] = None
    model_local_files_only: bool = False
    preload_model: bool = True

    # Config files
    skills_config_path: Path = BACKEND_DIR / "config" / "skills.json"
    scoring_config_path: Path = BACKEND_DIR / "config" / "scoring.json"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_file_size_bytes(self) -> int:
        return int(self.max_file_size_mb * 1024 * 1024)

    @property
    def max_docx_uncompressed_bytes(self) -> int:
        return int(self.max_docx_uncompressed_mb * 1024 * 1024)

    @property
    def max_request_bytes(self) -> int:
        """Upper bound for a whole multipart request (files plus form overhead)."""
        return self.max_files_per_request * self.max_file_size_bytes + 2 * 1024 * 1024


class ScoreWeights(BaseModel):
    required_skills: float = Field(ge=0)
    preferred_skills: float = Field(ge=0)
    semantic_similarity: float = Field(gt=0, description="Must be > 0: it is the fallback signal.")


class SemanticNormalization(BaseModel):
    floor: float = 0.0
    ceiling: float = 1.0

    @model_validator(mode="after")
    def _check(self) -> "SemanticNormalization":
        if self.ceiling <= self.floor:
            raise ValueError("semantic.ceiling must be greater than semantic.floor")
        return self


class ScoringConfig(BaseModel):
    version: str
    description: str = ""
    weights: ScoreWeights
    semantic: SemanticNormalization = SemanticNormalization()


def load_scoring_config(path: Path) -> ScoringConfig:
    with open(path, "r", encoding="utf-8") as fh:
        return ScoringConfig.model_validate(json.load(fh))


def get_settings() -> Settings:
    return Settings()
