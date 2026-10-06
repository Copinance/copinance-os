"""Canonical-facts market analysis must run the real tools, not just reach them.

The executor used to hand ``financial_literacy=None`` to every tool, whose parameter
validation rejects ``None`` for a string parameter. Mocking the tools hides that, so this
drives the real executor and tools against synthetic providers.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from math import sin
from typing import Any

import pytest

from copinance_os.core.execution_engine.market_analysis import MarketAnalysisExecutor
from copinance_os.domain.models.analysis import MARKET_DETERMINISTIC_TYPE, AnalysisOutputMode
from copinance_os.domain.models.job import Job, JobScope, JobTimeframe
from copinance_os.domain.models.market import MarketDataPoint
from copinance_os.domain.models.market.macro import MacroDataPoint
from copinance_os.domain.ports.data_providers import (
    MacroeconomicDataProvider,
    MarketDataProvider,
)

_DAYS = 400


class _SyntheticMarketProvider(MarketDataProvider):
    async def is_available(self) -> bool:
        return True

    def get_provider_name(self) -> str:
        return "synthetic-market"

    async def get_quote(self, symbol: str) -> dict[str, Any]:
        return {"symbol": symbol, "price": 100.0}

    async def get_historical_data(
        self, symbol: str, start_date: datetime, end_date: datetime, interval: str = "1d"
    ) -> list[MarketDataPoint]:
        end = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        points: list[MarketDataPoint] = []
        for i in range(_DAYS):
            close = Decimal(str(round(100 + i * 0.2 + 3 * sin(i / 5), 4)))
            points.append(
                MarketDataPoint(
                    symbol=symbol,
                    timestamp=end - timedelta(days=_DAYS - i),
                    open_price=close,
                    close_price=close,
                    high_price=close + 1,
                    low_price=close - 1,
                    volume=1_000_000,
                )
            )
        return points

    async def get_intraday_data(self, symbol: str, interval: str = "1min") -> list[MarketDataPoint]:
        return []

    async def search_instruments(
        self, query: str, limit: int = 10, quote_types: Any = None
    ) -> list[dict[str, Any]]:
        return []

    async def get_options_chain(self, underlying_symbol: str, expiration_date: str | None = None):  # type: ignore[no-untyped-def]
        raise NotImplementedError


class _SyntheticMacroProvider(MacroeconomicDataProvider):
    async def is_available(self) -> bool:
        return True

    def get_provider_name(self) -> str:
        return "synthetic-macro"

    async def get_time_series(
        self,
        series_id: str,
        start_date: datetime,
        end_date: datetime,
        *,
        frequency: str | None = None,
    ) -> list[MacroDataPoint]:
        end = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        return [
            MacroDataPoint(
                series_id=series_id,
                timestamp=end - timedelta(days=_DAYS - i),
                value=Decimal(str(round(20 + 2 * sin(i / 7), 4))),
            )
            for i in range(_DAYS)
        ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_canonical_facts_run_real_regime_tools_without_audience() -> None:
    executor = MarketAnalysisExecutor(
        market_data_provider=_SyntheticMarketProvider(),
        macro_data_provider=_SyntheticMacroProvider(),
    )
    job = Job(
        scope=JobScope.MARKET,
        market_type=None,
        instrument_symbol=None,
        market_index="SPY",
        timeframe=JobTimeframe.MID_TERM,
        execution_type=MARKET_DETERMINISTIC_TYPE,
    )

    results = await executor.execute(
        job,
        {
            "market_index": "SPY",
            "lookback_days": 252,
            "output_mode": AnalysisOutputMode.CANONICAL_FACTS.value,
        },
    )

    assert results["error"] is None
    assert "financial_literacy must be a string" not in repr(results)
    regime = results["market_regime_detection"]
    assert regime["detect_market_trend"]["regime"] == "bull"
    assert regime["detect_volatility_regime"] is not None
    assert regime["detect_market_cycles"] is not None
    assert results["market_regime_indicators"]["success"] is True
    assert results["market_regime_indicators"]["data"]["vix"]["available"] is True
    assert results["macro_regime_indicators"]["success"] is True
