"""Tool-selection eval: two tiers over the same 40-case dataset
(tool_selection_cases.py) and the same run_tool_selection_eval runner.

Fake-provider tier (below, always runs): validates the harness itself —
comparison/aggregation logic, dataset shape — deterministically and fast. It
does NOT test model judgment; see the module docstring on tool_selection.py.

Real-model tier (test_real_model_tool_selection_smoke): opt-in, @pytest.mark.llm,
skipped unless COPINANCEOS_GEMINI_API_KEY or COPINANCEOS_OPENAI_API_KEY is set.
Drives an actual provider against a representative subset of the market-data
tool family (the tools a lightweight fake MarketDataProvider can back) and
asserts a lenient pass-rate threshold — a real judgment smoke check, not a
strict release gate.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest

from copinance_os.ai.llm.eval import ToolSelectionCase, run_tool_selection_eval
from copinance_os.ai.llm.providers.base import LLMProvider
from copinance_os.ai.llm.providers.gemini import GeminiProvider
from copinance_os.ai.llm.providers.openai import OpenAIProvider
from copinance_os.core.pipeline.tools.data_provider.market_data import (
    MarketDataGetHistoricalDataTool,
    MarketDataGetOptionsChainTool,
    MarketDataGetQuoteTool,
    MarketDataOptionsPositioningTool,
    MarketDataSearchInstrumentsTool,
)
from copinance_os.domain.models.market.types import (
    MarketDataPoint,
    OptionContract,
    OptionsChain,
    OptionSide,
)
from copinance_os.domain.ports.data_providers import MarketDataProvider
from copinance_os.domain.ports.tools import Tool

from .tool_selection_cases import TOOL_SELECTION_CASES


def test_dataset_has_around_forty_cases_with_unique_ids() -> None:
    assert 35 <= len(TOOL_SELECTION_CASES) <= 45
    ids = [c.id for c in TOOL_SELECTION_CASES]
    assert len(ids) == len(set(ids))


def test_every_case_has_at_least_one_expected_tool() -> None:
    for case in TOOL_SELECTION_CASES:
        assert case.expected_tools, f"case {case.id!r} has no expected tools"


# ---------------------------------------------------------------------------
# Fake-provider tier: harness mechanics, not model judgment.
# ---------------------------------------------------------------------------


class _FakeScriptedProvider(LLMProvider):
    """Returns a canned tool-call list per question — no real inference."""

    def __init__(self, script: dict[str, list[str]]) -> None:
        self._script = script

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        return "fake text"

    async def is_available(self) -> bool:
        return True

    def get_provider_name(self) -> str:
        return "fake-scripted"

    async def generate_with_tools(
        self,
        prompt: str,
        tools: list[Tool] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        max_iterations: int = 5,
        **kwargs: Any,
    ) -> dict[str, Any]:
        called = self._script.get(prompt, [])
        return {
            "text": "fake answer",
            "tool_calls": [{"tool": name, "success": True} for name in called],
            "iterations": 1,
        }


@pytest.mark.asyncio
async def test_fake_provider_tier_scores_exact_match_as_passing() -> None:
    case = TOOL_SELECTION_CASES[0]
    provider = _FakeScriptedProvider({case.question: sorted(case.expected_tools)})

    report = await run_tool_selection_eval(provider, tools=[], cases=[case])

    assert report.pass_rate == 1.0
    assert report.results[0].passed is True


@pytest.mark.asyncio
async def test_fake_provider_tier_flags_missing_tool() -> None:
    case = ToolSelectionCase(
        id="missing-case",
        question="q",
        expected_tools=frozenset({"get_market_quote", "get_options_positioning"}),
    )
    provider = _FakeScriptedProvider({"q": ["get_market_quote"]})

    report = await run_tool_selection_eval(provider, tools=[], cases=[case])

    assert report.pass_rate == 0.0
    assert report.results[0].missing == frozenset({"get_options_positioning"})
    assert report.results[0].unexpected == frozenset()


@pytest.mark.asyncio
async def test_fake_provider_tier_flags_unexpected_tool() -> None:
    case = ToolSelectionCase(
        id="unexpected-case", question="q", expected_tools=frozenset({"get_market_quote"})
    )
    provider = _FakeScriptedProvider({"q": ["get_market_quote", "get_options_chain"]})

    report = await run_tool_selection_eval(provider, tools=[], cases=[case])

    assert report.pass_rate == 0.0
    assert report.results[0].unexpected == frozenset({"get_options_chain"})


@pytest.mark.asyncio
async def test_fake_provider_tier_allows_acceptable_extra_tools() -> None:
    case = ToolSelectionCase(
        id="alt-case",
        question="q",
        expected_tools=frozenset({"get_sec_fund_portfolio"}),
        acceptable_extra_tools=frozenset({"find_sec_funds"}),
    )
    provider = _FakeScriptedProvider({"q": ["get_sec_fund_portfolio", "find_sec_funds"]})

    report = await run_tool_selection_eval(provider, tools=[], cases=[case])

    assert report.pass_rate == 1.0


@pytest.mark.asyncio
async def test_fake_provider_tier_records_error_as_a_failure_not_a_crash() -> None:
    class _RaisingProvider(_FakeScriptedProvider):
        async def generate_with_tools(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("provider exploded")

    case = TOOL_SELECTION_CASES[0]
    report = await run_tool_selection_eval(_RaisingProvider({}), tools=[], cases=[case])

    assert report.pass_rate == 0.0
    assert report.results[0].error == "provider exploded"


@pytest.mark.asyncio
async def test_fake_provider_tier_runs_the_full_forty_case_dataset_end_to_end() -> None:
    """Every case's exact expected set, scripted verbatim -> the whole dataset
    passes. Guards against a case whose fields don't round-trip cleanly
    through the runner (e.g. a typo'd tool name)."""
    script = {c.question: sorted(c.expected_tools) for c in TOOL_SELECTION_CASES}
    provider = _FakeScriptedProvider(script)

    report = await run_tool_selection_eval(provider, tools=[], cases=TOOL_SELECTION_CASES)

    assert report.pass_rate == 1.0, report.summary()


# ---------------------------------------------------------------------------
# Real-model tier: opt-in, needs an API key, actual judgment is measured here.
# ---------------------------------------------------------------------------


class _FakeMarketDataProvider(MarketDataProvider):
    """Minimal synthetic backing so a real LLM's tool calls return plausible
    data instead of provider errors, for the smoke-check subset of tools."""

    async def is_available(self) -> bool:
        return True

    def get_provider_name(self) -> str:
        return "fake-market-data"

    async def get_quote(self, symbol: str) -> dict[str, Any]:
        return {"symbol": symbol, "price": 123.45, "currency": "USD"}

    async def get_historical_data(
        self, symbol: str, start_date: datetime, end_date: datetime, interval: str = "1d"
    ) -> list[MarketDataPoint]:
        return [
            MarketDataPoint(
                symbol=symbol,
                timestamp=start_date,
                open_price=Decimal("100"),
                close_price=Decimal("101"),
                high_price=Decimal("102"),
                low_price=Decimal("99"),
                volume=1_000_000,
            )
        ]

    async def get_intraday_data(self, symbol: str, interval: str = "1min") -> list[MarketDataPoint]:
        return []

    async def search_instruments(
        self, query: str, limit: int = 10, quote_types: Any = None
    ) -> list[dict[str, Any]]:
        return [{"symbol": query.upper(), "name": f"{query.title()} Inc.", "exchange": "NASDAQ"}]

    async def get_options_chain(
        self, underlying_symbol: str, expiration_date: str | None = None
    ) -> OptionsChain:
        exp = date(2027, 1, 15)
        contract = OptionContract(
            underlying_symbol=underlying_symbol,
            contract_symbol=f"{underlying_symbol}270115C00100000",
            side=OptionSide.CALL,
            strike=Decimal("100"),
            expiration_date=exp,
            last_price=None,
            bid=Decimal("1.0"),
            ask=Decimal("1.2"),
            volume=None,
            open_interest=None,
            implied_volatility=None,
            in_the_money=None,
            currency="USD",
            greeks=None,
        )
        return OptionsChain(
            underlying_symbol=underlying_symbol,
            expiration_date=exp,
            available_expirations=[exp],
            underlying_price=Decimal("100"),
            calls=[contract],
            puts=[contract],
            currency="USD",
        )


def _build_smoke_provider() -> LLMProvider | None:
    gemini_key = os.environ.get("COPINANCEOS_GEMINI_API_KEY", "").strip()
    openai_key = os.environ.get("COPINANCEOS_OPENAI_API_KEY", "").strip()
    if gemini_key:
        return GeminiProvider(api_key=gemini_key)
    if openai_key:
        return OpenAIProvider(api_key=openai_key)
    return None


_SMOKE_CASE_IDS = {
    "quote-current-price",
    "historical-30-day-close",
    "search-by-name",
    "options-chain-single-expiry",
    "positioning-bias",
}


@pytest.mark.llm
@pytest.mark.asyncio
async def test_real_model_tool_selection_smoke() -> None:
    provider = _build_smoke_provider()
    if provider is None:
        pytest.skip(
            "No LLM API key configured (COPINANCEOS_GEMINI_API_KEY / "
            "COPINANCEOS_OPENAI_API_KEY) — real-model eval tier is opt-in."
        )

    data_provider = _FakeMarketDataProvider()
    tools: list[Tool] = [
        MarketDataGetQuoteTool(data_provider),
        MarketDataGetHistoricalDataTool(data_provider),
        MarketDataSearchInstrumentsTool(data_provider),
        MarketDataGetOptionsChainTool(data_provider),
        MarketDataOptionsPositioningTool(data_provider),
    ]
    cases = [c for c in TOOL_SELECTION_CASES if c.id in _SMOKE_CASE_IDS]

    report = await run_tool_selection_eval(provider, tools=tools, cases=cases)

    assert report.pass_rate >= 0.6, report.summary()
