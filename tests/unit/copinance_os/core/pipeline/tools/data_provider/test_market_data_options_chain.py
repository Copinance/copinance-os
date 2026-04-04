"""Unit tests for get_options_chain LLM tool."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from copinance_os.core.pipeline.tools.data_provider.market_data import MarketDataGetOptionsChainTool
from copinance_os.domain.models.market import OptionContract, OptionsChain, OptionSide


def _chain_for_expiry(expiry: date) -> OptionsChain:
    return OptionsChain(
        underlying_symbol="AAPL",
        expiration_date=expiry,
        available_expirations=[expiry],
        underlying_price=Decimal("180"),
        calls=[
            OptionContract(
                underlying_symbol="AAPL",
                contract_symbol="AAPL-C",
                side=OptionSide.CALL,
                strike=Decimal("180"),
                expiration_date=expiry,
                last_price=Decimal("5"),
            )
        ],
        puts=[],
    )


@pytest.mark.unit
async def test_get_options_chain_tool_multiple_expirations() -> None:
    provider = AsyncMock()
    provider.get_provider_name = lambda: "test"
    provider.get_options_chain = AsyncMock(
        side_effect=lambda underlying_symbol, expiration_date=None: _chain_for_expiry(
            date.fromisoformat(expiration_date) if expiration_date else date(2026, 6, 20)
        )
    )
    tool = MarketDataGetOptionsChainTool(provider, cache_manager=None, use_cache=False)

    result = await tool.execute(
        underlying_symbol="AAPL",
        expiration_dates=["2026-06-19", "2026-07-17"],
        option_side="all",
    )

    assert result.success
    assert result.data is not None
    assert result.data.get("multi_expiration") is True
    assert len(result.data.get("expirations") or []) == 2
    assert provider.get_options_chain.await_count == 2


@pytest.mark.unit
async def test_get_options_chain_tool_single_expiration_legacy_shape() -> None:
    provider = AsyncMock()
    provider.get_provider_name = lambda: "test"
    provider.get_options_chain = AsyncMock(return_value=_chain_for_expiry(date(2026, 6, 19)))
    tool = MarketDataGetOptionsChainTool(provider, cache_manager=None, use_cache=False)

    result = await tool.execute(underlying_symbol="AAPL", expiration_date="2026-06-19")

    assert result.success
    assert result.data is not None
    assert "multi_expiration" not in result.data
    assert result.data.get("expiration_date") == "2026-06-19"
    provider.get_options_chain.assert_awaited_once()
