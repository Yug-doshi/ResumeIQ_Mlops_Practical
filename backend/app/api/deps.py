from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from app.config import ScoringConfig, Settings
from app.services.matching_service import MatchingService
from app.services.semantic_matcher import SemanticMatcher
from app.services.skill_extractor import SkillExtractor


@dataclass
class ServiceContainer:
    settings: Settings
    extractor: SkillExtractor
    matcher: SemanticMatcher
    scoring_config: ScoringConfig
    matching_service: MatchingService


def get_services(request: Request) -> ServiceContainer:
    return request.app.state.services
