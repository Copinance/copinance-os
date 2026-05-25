"""Unit tests for CuratedQuestionsGenerator."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from copinance_os.ai.curated_questions.generator import CuratedQuestionsGenerator
from copinance_os.domain.models.curated_questions import (
    ArtifactType,
    LLMUnavailableReason,
)


@pytest.mark.unit
async def test_generator_no_provider_returns_no_llm_config() -> None:
    gen = CuratedQuestionsGenerator(allowed_tool_names=frozenset({"get_market_quote"}))
    block = await gen.generate(
        artifact=ArtifactType.QUOTE,
        context_summary={"symbol": "SPY"},
        count=3,
        financial_literacy=None,
        learning_step=None,
        llm_provider=None,
    )
    assert block.questions == []
    assert block.meta.llm_unavailable_reason == LLMUnavailableReason.NO_LLM_CONFIG


@pytest.mark.unit
async def test_generator_configured_but_unavailable_returns_provider_error() -> None:
    provider = MagicMock()
    provider.is_available = AsyncMock(return_value=False)
    gen = CuratedQuestionsGenerator(allowed_tool_names=frozenset({"get_market_quote"}))
    block = await gen.generate(
        artifact=ArtifactType.QUOTE,
        context_summary={"symbol": "SPY"},
        count=3,
        financial_literacy=None,
        learning_step=None,
        llm_provider=provider,
    )
    assert block.questions == []
    assert block.meta.llm_unavailable_reason == LLMUnavailableReason.PROVIDER_ERROR


@pytest.mark.unit
async def test_generator_parses_json_and_filters_tools() -> None:
    provider = MagicMock()
    provider.is_available = AsyncMock(return_value=True)
    provider.generate_text = AsyncMock(
        return_value='{"questions":[{"text":"What is IV skew?","suggested_tools":["get_market_quote","fake_tool"]}]}'
    )
    gen = CuratedQuestionsGenerator(
        allowed_tool_names=frozenset({"get_market_quote", "get_options_chain"}),
    )
    block = await gen.generate(
        artifact=ArtifactType.OPTIONS_CHAIN,
        context_summary={"underlying_symbol": "SPY"},
        count=3,
        financial_literacy=None,
        learning_step=None,
        llm_provider=provider,
    )
    assert len(block.questions) == 1
    assert block.meta.llm_enabled is True
    assert block.questions[0].suggested_tools == ["get_market_quote"]


@pytest.mark.unit
async def test_generator_parse_error() -> None:
    provider = MagicMock()
    provider.is_available = AsyncMock(return_value=True)
    provider.generate_text = AsyncMock(return_value="not json at all")
    gen = CuratedQuestionsGenerator(allowed_tool_names=frozenset())
    block = await gen.generate(
        artifact=ArtifactType.QUOTE,
        context_summary={},
        count=2,
        financial_literacy=None,
        learning_step=None,
        llm_provider=provider,
    )
    assert block.meta.llm_unavailable_reason == LLMUnavailableReason.PARSE_ERROR
