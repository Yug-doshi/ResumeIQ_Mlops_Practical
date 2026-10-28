
"""Orchestrates one matching request: parse -> extract -> embed -> score -> rank.

The service holds no per-user state and persists nothing; uploaded bytes live
in memory for the duration of the request only.

MLflow records aggregate metrics and model configuration without logging
resume text, filenames, candidate names, or personally identifiable data.
"""
from __future__ import annotations

import logging
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Optional

from mlops.tracking import track_matching_run

from app.config import ScoringConfig, Settings
from app.exceptions import ResumeParseError
from app.schemas import (
    CandidateResult,
    EvidenceSnippet,
    ExperienceInfo,
    ExperienceMention,
    FileError,
    JobInfo,
    JobRequirements,
    MatchResponse,
    ProcessingSummary,
)
from app.services.experience_extractor import extract_experience_mentions
from app.services.resume_parser import (
    ParsedResume,
    ParserLimits,
    extract_resume_text,
)
from app.services.scoring_service import compute_score, normalize_semantic
from app.services.semantic_matcher import SemanticMatcher
from app.services.skill_extractor import SkillExtractor

logger = logging.getLogger(__name__)

MAX_EVIDENCE_PER_SKILL = 2
MAX_EVIDENCE_TOTAL = 20


@contextmanager
def safe_tracking_run(**kwargs):
    """Attempt MLflow tracking without breaking resume matching."""
    try:
        with track_matching_run(**kwargs) as metrics:
            yield metrics
    except Exception:
        logger.exception(
            "MLflow tracking failed; resume matching will continue."
        )
        yield {}


@dataclass
class UploadedResume:
    index: int
    filename: str
    content: Optional[bytes] = None
    precheck_error: Optional[ResumeParseError] = None


class MatchingService:
    def __init__(
        self,
        settings: Settings,
        extractor: SkillExtractor,
        matcher: SemanticMatcher,
        scoring_config: ScoringConfig,
    ):
        self.settings = settings
        self.extractor = extractor
        self.matcher = matcher
        self.scoring_config = scoring_config

        self.limits = ParserLimits(
            max_file_bytes=settings.max_file_size_bytes,
            max_docx_uncompressed_bytes=settings.max_docx_uncompressed_bytes,
            max_pdf_pages=settings.max_pdf_pages,
            max_extracted_chars=settings.max_extracted_chars,
            min_extracted_chars=settings.min_extracted_chars,
        )

    def run(
        self,
        job: JobRequirements,
        uploads: list[UploadedResume],
    ) -> MatchResponse:
        """Execute matching and record aggregate metrics in MLflow."""
        with safe_tracking_run(
            model_name=self.matcher.model_id,
            scoring_version=self.scoring_config.version,
            skill_dictionary_version=self.extractor.dictionary.version,
            uploaded_count=len(uploads),
        ) as metrics:
            started = perf_counter()

            response = self._run_without_tracking(job, uploads)

            metrics["processed_count"] = response.summary.processed
            metrics["failed_count"] = response.summary.failed
            metrics["candidate_count"] = (
                response.summary.candidates_with_results
            )

            if response.summary.average_score is not None:
                metrics["average_matching_score"] = (
                    response.summary.average_score
                )

            metrics["matching_duration_seconds"] = (
                perf_counter() - started
            )

            return response

    def _run_without_tracking(
        self,
        job: JobRequirements,
        uploads: list[UploadedResume],
    ) -> MatchResponse:
        """Perform the original matching workflow."""
        request_id = uuid.uuid4().hex[:12]

        required = self.extractor.normalize_requirements(
            job.required_skills
        )

        required_lower = {skill.lower() for skill in required}

        preferred = [
            skill
            for skill in self.extractor.normalize_requirements(
                job.preferred_skills
            )
            if skill.lower() not in required_lower
        ]

        parsed: list[tuple[UploadedResume, ParsedResume]] = []
        errors: list[FileError] = []

        # Parse uploaded resumes.
        for upload in uploads:
            try:
                if upload.precheck_error is not None:
                    raise upload.precheck_error

                resume = extract_resume_text(
                    upload.filename,
                    upload.content or b"",
                    self.limits,
                )
                parsed.append((upload, resume))

            except ResumeParseError as exc:
                errors.append(
                    FileError(
                        upload_index=upload.index,
                        filename=upload.filename,
                        code=exc.code,
                        message=exc.message,
                    )
                )

            except Exception:
                logger.exception(
                    "Unexpected parse failure "
                    "(request=%s file_index=%s)",
                    request_id,
                    upload.index,
                )

                errors.append(
                    FileError(
                        upload_index=upload.index,
                        filename=upload.filename,
                        code="parse_failed",
                        message="The file could not be processed.",
                    )
                )

        candidates: list[CandidateResult] = []

        # Calculate semantic similarity and score candidates.
        if parsed:
            query = f"{job.job_title}\n{job.job_description}"

            cosines = self.matcher.calculate_semantic_similarity(
                query,
                [resume.text for _, resume in parsed],
            )

            for (upload, resume), cosine in zip(parsed, cosines):
                candidates.append(
                    self._build_candidate(
                        job,
                        required,
                        preferred,
                        upload,
                        resume,
                        cosine,
                    )
                )

        # Rank candidates by final score, then semantic score.
        candidates.sort(
            key=lambda candidate: (
                -candidate.score,
                -candidate.semantic_score,
                candidate.upload_index,
            )
        )

        for rank, candidate in enumerate(candidates, start=1):
            candidate.rank = rank

        average = (
            round(
                sum(candidate.score for candidate in candidates)
                / len(candidates),
                2,
            )
            if candidates
            else None
        )

        logger.info(
            "Match request %s: uploaded=%d processed=%d failed=%d "
            "error_codes=%s",
            request_id,
            len(uploads),
            len(candidates),
            len(errors),
            sorted({error.code for error in errors}),
        )

        return MatchResponse(
            request_id=request_id,
            generated_at=datetime.now(timezone.utc).isoformat(),
            job=JobInfo(
                job_title=job.job_title,
                description_characters=len(job.job_description),
                required_skills=required,
                preferred_skills=preferred,
                min_experience_years=job.min_experience_years,
                education_requirement=job.education_requirement,
            ),
            model_id=self.matcher.model_id,
            scoring_version=self.scoring_config.version,
            skill_dictionary_version=self.extractor.dictionary.version,
            summary=ProcessingSummary(
                total_uploaded=len(uploads),
                processed=len(candidates),
                failed=len(errors),
                candidates_with_results=len(candidates),
                average_score=average,
            ),
            candidates=candidates,
            errors=sorted(
                errors,
                key=lambda error: error.upload_index,
            ),
        )

    def _build_candidate(
        self,
        job: JobRequirements,
        required: list[str],
        preferred: list[str],
        upload: UploadedResume,
        resume: ParsedResume,
        cosine: float,
    ) -> CandidateResult:
        text = resume.text

        req_matched = [
            skill
            for skill in required
            if self.extractor.contains_skill(text, skill)
        ]

        pref_matched = [
            skill
            for skill in preferred
            if self.extractor.contains_skill(text, skill)
        ]

        req_missing = [
            skill for skill in required if skill not in req_matched
        ]

        pref_missing = [
            skill for skill in preferred if skill not in pref_matched
        ]

        extracted = self.extractor.extract_skills(text)
        known = {skill.lower() for skill in extracted}

        extracted += [
            skill
            for skill in [*req_matched, *pref_matched]
            if skill.lower() not in known
        ]

        breakdown = compute_score(
            required_total=len(required),
            required_matched=len(req_matched),
            preferred_total=len(preferred),
            preferred_matched=len(pref_matched),
            semantic_cosine=cosine,
            config=self.scoring_config,
        )

        sem_cfg = self.scoring_config.semantic

        semantic_score = round(
            normalize_semantic(
                cosine,
                sem_cfg.floor,
                sem_cfg.ceiling,
            )
            * 100,
            2,
        )

        evidence: list[EvidenceSnippet] = []

        for skill in [*req_matched, *pref_matched]:
            for item in self.extractor.find_evidence(
                text,
                skill,
                max_snippets=MAX_EVIDENCE_PER_SKILL,
            ):
                evidence.append(
                    EvidenceSnippet(
                        skill=item.skill,
                        snippet=item.snippet,
                        line=item.line,
                    )
                )

            if len(evidence) >= MAX_EVIDENCE_TOTAL:
                break

        return CandidateResult(
            resume_id=uuid.uuid4().hex[:10],
            rank=0,
            upload_index=upload.index,
            filename=upload.filename,
            score=breakdown.final_score,
            semantic_score=semantic_score,
            semantic_cosine=round(cosine, 4),
            required_matched=req_matched,
            required_not_found=req_missing,
            preferred_matched=pref_matched,
            preferred_not_found=pref_missing,
            extracted_skills=extracted,
            score_breakdown=breakdown,
            evidence=evidence[:MAX_EVIDENCE_TOTAL],
            experience=self._experience(
                job.min_experience_years,
                text,
            ),
            warnings=list(resume.warnings),
            extracted_characters=len(text),
            model_id=self.matcher.model_id,
        )

    @staticmethod
    def _experience(
        required_years: Optional[float],
        text: str,
    ) -> ExperienceInfo:
        if required_years is None:
            return ExperienceInfo(
                status="not_requested",
                note="No minimum experience was specified.",
            )

        mentions = extract_experience_mentions(text)

        if not mentions:
            return ExperienceInfo(
                required_years=required_years,
                status="no_explicit_mention",
                note=(
                    "The resume has no explicit 'N years of experience' "
                    "statement. Experience may still be evident from job "
                    "dates; review manually. Experience is not part of "
                    "the score."
                ),
            )

        return ExperienceInfo(
            required_years=required_years,
            status="mentions_found",
            max_stated_years=max(mention.years for mention in mentions),
            mentions=[
                ExperienceMention(
                    years=mention.years,
                    snippet=mention.snippet,
                    line=mention.line,
                )
                for mention in mentions
            ],
            note=(
                "Statements are quoted from the resume and are unverified. "
                "They may refer to a single skill rather than total "
                "experience. Experience is not part of the score."
            ),
        )
