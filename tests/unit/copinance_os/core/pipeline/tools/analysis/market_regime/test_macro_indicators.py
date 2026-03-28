"""Unit tests for macro regime indicators tool."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from copinance_os.core.pipeline.tools.analysis.market_regime.macro_indicators import (
    MacroRegimeIndicatorsTool,
)
from copinance_os.domain.models.market import MarketDataPoint, OptionsChain


class _FailingMacroProvider:
    def get_provider_name(self) -> str:
        return "fred"

    async def is_available(self) -> bool:
        return False

    async def get_time_series(self, *args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("FRED down")


class _StubMarketProvider:
    def get_provider_name(self) -> str:
        return "yfinance"

    async def is_available(self) -> bool:
        return True

    async def get_quote(self, symbol: str) -> dict[str, Any]:
        return {"symbol": symbol}

    async def get_intraday_data(self, symbol: str, interval: str = "1min") -> list[MarketDataPoint]:
        return []

    async def search_instruments(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        return []

    async def get_options_chain(
        self, underlying_symbol: str, expiration_date: str | None = None
    ) -> OptionsChain:
        raise RuntimeError("Options not used in this test")

    async def get_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
    ) -> list[MarketDataPoint]:
        # Provide minimal proxy data for ^TNX and USO; anything else empty.
        ts = datetime(2025, 1, 5, tzinfo=UTC)

        def _mk(close: Decimal) -> MarketDataPoint:
            return MarketDataPoint(
                symbol=symbol,
                timestamp=ts,
                open_price=close,
                close_price=close,
                high_price=close,
                low_price=close,
                volume=0,
                metadata={},
            )

        if symbol == "^TNX":
            return [_mk(Decimal("45.0"))]  # 4.5% after /10
        if symbol == "USO":
            return [_mk(Decimal("80.0"))]
        if symbol in {"HYG", "LQD"}:
            return [_mk(Decimal("100.0"))]
        return []


@pytest.mark.unit
class TestMacroRegimeIndicatorsTool:
    @pytest.mark.asyncio
    async def test_falls_back_to_yfinance_when_fred_fails(self) -> None:
        tool = MacroRegimeIndicatorsTool(_FailingMacroProvider(), _StubMarketProvider())  # type: ignore[arg-type]
        result = await tool.execute(lookback_days=30)

        assert result.success is True
        assert result.data is not None
        assert result.data["rates"]["source"] == "yfinance"
        assert result.data["credit"]["source"] == "yfinance"
        assert result.data["commodities"]["source"] == "yfinance"
