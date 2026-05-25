"""Unit tests for GenerateCuratedQuestionsUseCase."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from copinance_os.ai.curated_questions.generator import CuratedQuestionsGenerator
from copinance_os.data.cache.cache_manager import CacheManager
from copinance_os.domain.models.curated.questions import (
    ArtifactType,
    CuratedQuestionsBlock,
    CuratedQuestionsMeta,
    GenerateCuratedQuestionsRequest,
    LLMUnavailableReason,
)
from copinance_os.domain.ports.storage import CacheEntry
from copinance_os.research.workflows.curated_questions import GenerateCuratedQuestionsUseCase


def _empty_block() -> CuratedQuestionsBlock:
    return CuratedQuestionsBlock(
        questions=[],
        meta=CuratedQuestionsMeta(
            artifact=ArtifactType.QUOTE,
            requested_count=3,
            llm_enabled=False,
            llm_unavailable_reason=LLMUnavailableReason.NO_LLM_CONFIG,
            numeric_grounding_policy="policy",
        ),
    )


@pytest.mark.unit
async def test_use_case_cache_hit_skips_generator() -> None:
    backend = MagicMock()
    cached = _empty_block().model_dump(mode="json")
    entry = CacheEntry(
        schema_version="1",
        data=cached,
        cached_at=datetime.now(UTC),
        tool_name="curated_questions",
        cache_key="k",
        metadata={},
    )
    backend.get = AsyncMock(return_value=entry)
    backend.set = AsyncMock()
    cache = CacheManager(backend=backend)

    generator = MagicMock(spec=CuratedQuestionsGenerator)
    generator.generate = AsyncMock()

    uc = GenerateCuratedQuestionsUseCase(
        generator=generator,
        cache_manager=cache,
        llm_provider=None,
    )
    result = await uc.execute(
        GenerateCuratedQuestionsRequest(
            artifact=ArtifactType.QUOTE,
            payload={"symbol": "SPY", "current_price": 100},
            count=3,
        )
    )
    assert result.meta.cache_hit is True
    generator.generate.assert_not_called()


@pytest.mark.unit
async def test_use_case_llm_provider_override_passed() -> None:
    backend = MagicMock()
    backend.get = AsyncMock(return_value=None)
    backend.set = AsyncMock()
    cache = CacheManager(backend=backend)

    generator = MagicMock(spec=CuratedQuestionsGenerator)
    generator.generate = AsyncMock(return_value=_empty_block())

    override = MagicMock()
    default = MagicMock()

    uc = GenerateCuratedQuestionsUseCase(
        generator=generator,
        cache_manager=cache,
        llm_provider=default,
    )
    await uc.execute(
        GenerateCuratedQuestionsRequest(
            artifact=ArtifactType.QUOTE,
            payload={"symbol": "AAPL"},
            count=2,
            no_cache=True,
        ),
        llm_provider_override=override,
    )
    call_kwargs = generator.generate.call_args.kwargs
    assert call_kwargs["llm_provider"] is override
