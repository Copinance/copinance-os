"""Integration: curated questions use case via DI container."""

from __future__ import annotations

import pytest

from copinance_os.domain.exceptions import ValidationError
from copinance_os.domain.models.curated.questions import (
    ArtifactType,
    GenerateCuratedQuestionsRequest,
    LLMUnavailableReason,
)
from copinance_os.domain.models.entities.profile import FinancialLiteracy
from copinance_os.infra.di import get_container, reset_container


@pytest.mark.integration
async def test_container_generate_curated_questions_quote_payload() -> None:
    """End-to-end wiring: container → use case → validate → generate (no LLM key in CI)."""
    reset_container()
    container = get_container()
    use_case = container.generate_curated_questions_use_case()

    block = await use_case.execute(
        GenerateCuratedQuestionsRequest(
            artifact=ArtifactType.QUOTE,
            payload={"symbol": "SPY", "current_price": 500, "volume": 1_000_000},
            count=3,
            financial_literacy=FinancialLiteracy.INTERMEDIATE,
            no_cache=True,
        )
    )

    assert block.meta.artifact == ArtifactType.QUOTE
    assert block.meta.requested_count == 3
    assert block.meta.numeric_grounding_policy
    assert block.meta.cache_hit is False
    # CI typically has no valid LLM key — either questions or typed fallback
    if not block.meta.llm_enabled:
        assert block.questions == []
        assert block.meta.llm_unavailable_reason in (
            LLMUnavailableReason.NO_LLM_CONFIG,
            LLMUnavailableReason.PROVIDER_ERROR,
        )
    else:
        assert len(block.questions) <= 3
        for q in block.questions:
            assert q.text.strip()
            if q.suggested_tools:
                for tool in q.suggested_tools:
                    assert tool.isidentifier() or "_" in tool


@pytest.mark.integration
async def test_container_rejects_invalid_sector_payload() -> None:
    reset_container()
    use_case = get_container().generate_curated_questions_use_case()

    with pytest.raises(ValidationError):
        await use_case.execute(
            GenerateCuratedQuestionsRequest(
                artifact=ArtifactType.SECTOR_ROTATION,
                payload={"sectors": []},
                count=2,
                no_cache=True,
            )
        )
