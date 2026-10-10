"""Orchestrates one matching request: parse -> extract -> embed -> score -> rank.

The service holds no per-user state and persists nothing; uploaded bytes live
in memory for the duration of the request only.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

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
from app.services.resume_parser import ParsedResume, ParserLimits, extract_resume_text
from app.services.scoring_service import compute_score, normalize_semantic
from app.services.semantic_matcher import SemanticMatcher
from app.services.skill_extractor import SkillExtractor

logger = logging.getLogger(__name__)

MAX_EVIDENCE_PER_SKILL = 2
MAX_EVIDENCE_TOTAL = 20


@dataclass
class UploadedResume:
    index: int
    filename: str
    content: Optional[bytes] = None
    precheck_error: Optional[ResumeParseError] = None  # e.g. size exceeded while reading


class MatchingService:
    def __init__(self, settings: Settings, extractor: SkillExtractor, matcher: SemanticMatcher,
                 scoring_config: ScoringConfig):
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

    def run(self, job: JobRequirements, uploads: list[UploadedResume]) -> MatchResponse:
        request_id = uuid.uuid4().hex[:12]
        required = self.extractor.normalize_requirements(job.required_skills)
        preferred = [s for s in self.extractor.normalize_requirements(job.preferred_skills)
                     if s.lower() not in {r.lower() for r in required}]

        parsed: list[tuple[UploadedResume, ParsedResume]] = []
        errors: list[FileError] = []
        for upload in uploads:
            try:
                if upload.precheck_error is not None:
                    raise upload.precheck_error
                parsed.append((upload, extract_resume_text(upload.filename, upload.content or b"", self.limits)))
            except ResumeParseError as exc:
                errors.append(FileError(upload_index=upload.index, filename=upload.filename,
                                        code=exc.code, message=exc.message))
            except Exception:
                logger.exception("Unexpected parse failure (request=%s file_index=%s)", request_id, upload.index)
                errors.append(FileError(upload_index=upload.index, filename=upload.filename,
                                        code="parse_failed", message="The file could not be processed."))

        candidates: list[CandidateResult] = []
        if parsed:
            # Title + description only: skill lists are scored separately, so they are not repeated here.
            query = f"{job.job_title}\n{job.job_description}"
            cosines = self.matcher.calculate_semantic_similarity(query, [p.text for _, p in parsed])
            for (upload, resume), cosine in zip(parsed, cosines):
                candidates.append(self._build_candidate(job, required, preferred, upload, resume, cosine))

        candidates.sort(key=lambda c: (-c.score, -c.semantic_score, c.upload_index))
        for rank, candidate in enumerate(candidates, start=1):
            candidate.rank = rank

        average = round(sum(c.score for c in candidates) / len(candidates), 2) if candidates else None
        logger.info("Match request %s: uploaded=%d processed=%d failed=%d error_codes=%s", request_id,
                    len(uploads), len(candidates), len(errors), sorted({e.code for e in errors}))

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
            errors=sorted(errors, key=lambda e: e.upload_index),
        )

    def _build_candidate(self, job: JobRequirements, required: list[str], preferred: list[str],
                         upload: UploadedResume, resume: ParsedResume, cosine: float) -> CandidateResult:
        text = resume.text
        req_matched = [s for s in required if self.extractor.contains_skill(text, s)]
        pref_matched = [s for s in preferred if self.extractor.contains_skill(text, s)]
        req_missing = [s for s in required if s not in req_matched]
        pref_missing = [s for s in preferred if s not in pref_matched]

        extracted = self.extractor.extract_skills(text)
        known = {s.lower() for s in extracted}
        extracted += [s for s in [*req_matched, *pref_matched] if s.lower() not in known]

        breakdown = compute_score(
            required_total=len(required), required_matched=len(req_matched),
            preferred_total=len(preferred), preferred_matched=len(pref_matched),
            semantic_cosine=cosine, config=self.scoring_config,
        )
        sem_cfg = self.scoring_config.semantic
        semantic_score = round(normalize_semantic(cosine, sem_cfg.floor, sem_cfg.ceiling) * 100, 2)

        evidence: list[EvidenceSnippet] = []
        for skill in [*req_matched, *pref_matched]:
            for item in self.extractor.find_evidence(text, skill, max_snippets=MAX_EVIDENCE_PER_SKILL):
                evidence.append(EvidenceSnippet(skill=item.skill, snippet=item.snippet, line=item.line))
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
            experience=self._experience(job.min_experience_years, text),
            warnings=list(resume.warnings),
            extracted_characters=len(text),
            model_id=self.matcher.model_id,
        )

    @staticmethod
    def _experience(required_years: Optional[float], text: str) -> ExperienceInfo:
        if required_years is None:
            return ExperienceInfo(status="not_requested", note="No minimum experience was specified.")
        mentions = extract_experience_mentions(text)
        if not mentions:
            return ExperienceInfo(
                required_years=required_years, status="no_explicit_mention",
                note="The resume has no explicit 'N years of experience' statement. Experience may still be "
                     "evident from job dates; review manually. Experience is not part of the score.",
            )
        return ExperienceInfo(
            required_years=required_years, status="mentions_found",
            max_stated_years=max(m.years for m in mentions),
            mentions=[ExperienceMention(years=m.years, snippet=m.snippet, line=m.line) for m in mentions],
            note="Statements are quoted from the resume and are unverified. They may refer to a single skill "
                 "rather than total experience. Experience is not part of the score.",
        )
