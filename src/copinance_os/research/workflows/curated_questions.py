"""Generate curated follow-up questions from already-fetched data payloads."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import structlog

from copinance_os.ai.curated_questions.generator import CuratedQuestionsGenerator
from copinance_os.data.cache.cache_manager import CacheManager
from copinance_os.data.curated_questions.context import build_context
from copinance_os.data.curated_questions.limits import DASHBOARD_ARTIFACTS
from copinance_os.domain.literacy import resolve_financial_literacy
from copinance_os.domain.models.curated.questions import (
    ArtifactType,
    CuratedQuestion,
    CuratedQuestionsBlock,
    CuratedQuestionsMeta,
    GenerateCuratedQuestionsRequest,
    LLMUnavailableReason,
    curated_questions_cache_key_kwargs,
    validate_artifact_payload,
)
from copinance_os.research.workflows.base import UseCase

if TYPE_CHECKING:
    from copinance_os.ai.llm.providers.base import LLMProvider

# Re-export for consumers that import from this module
__all__ = [
    "ArtifactType",
    "CuratedQuestion",
    "CuratedQuestionsBlock",
    "CuratedQuestionsMeta",
    "GenerateCuratedQuestionsRequest",
    "GenerateCuratedQuestionsUseCase",
    "LLMUnavailableReason",
    "validate_artifact_payload",
]

logger = structlog.get_logger(__name__)

# Cache curated-questions LLM output only (not market data fetches). BFF may add its own TTL.
_CACHE_TOOL_NAME = "curated_questions"
_DASHBOARD_TTL = timedelta(minutes=5)
_SYMBOL_SNAPSHOT_TTL = timedelta(seconds=90)


def _ttl_for_artifact(artifact_value: str) -> timedelta:
    try:
        art = ArtifactType(artifact_value)
    except ValueError:
        return _SYMBOL_SNAPSHOT_TTL
    if art in DASHBOARD_ARTIFACTS:
        return _DASHBOARD_TTL
    return _SYMBOL_SNAPSHOT_TTL


class GenerateCuratedQuestionsUseCase(
    UseCase[GenerateCuratedQuestionsRequest, CuratedQuestionsBlock]
):
    """Generate LLM-curated follow-up questions from a validated data payload."""

    def __init__(
        self,
        generator: CuratedQuestionsGenerator,
        cache_manager: CacheManager,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self._generator = generator
        self._cache_manager = cache_manager
        self._llm_provider = llm_provider

    async def execute(
        self,
        request: GenerateCuratedQuestionsRequest,
        *,
        llm_provider_override: LLMProvider | None = None,
    ) -> CuratedQuestionsBlock:
        validated = validate_artifact_payload(request.artifact, request.payload)
        lit = resolve_financial_literacy(request.financial_literacy)
        literacy_value = lit.value

        cache_kwargs = curated_questions_cache_key_kwargs(
            artifact=request.artifact,
            payload=validated,
            literacy_value=literacy_value,
            count=request.count,
            learning_step=request.learning_step,
        )

        if not request.no_cache:
            entry = await self._cache_manager.get(_CACHE_TOOL_NAME, **cache_kwargs)
            if entry is not None and isinstance(entry.data, dict):
                try:
                    block = CuratedQuestionsBlock.model_validate(entry.data)
                    return block.model_copy(
                        update={
                            "meta": block.meta.model_copy(update={"cache_hit": True}),
                        }
                    )
                except Exception:
                    logger.debug("Curated questions cache entry invalid; regenerating")

        summary = build_context(request.artifact, validated)
        effective_llm = (
            llm_provider_override if llm_provider_override is not None else self._llm_provider
        )

        block = await self._generator.generate(
            artifact=request.artifact,
            context_summary=summary,
            count=request.count,
            financial_literacy=lit,
            learning_step=request.learning_step,
            llm_provider=effective_llm,
        )

        if block.meta.llm_enabled and not request.no_cache:
            await self._cache_manager.set(
                _CACHE_TOOL_NAME,
                data=block.model_dump(mode="json"),
                ttl=_ttl_for_artifact(request.artifact.value),
                **cache_kwargs,
            )

        return block
