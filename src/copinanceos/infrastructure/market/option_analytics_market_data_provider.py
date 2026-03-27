"""Composition: raw ``MarketDataProvider`` + option Greek estimation.

``infrastructure.data_providers`` contains vendor adapters only (Yahoo, EDGAR, FRED).
This module wires a source provider to domain analytics (``OptionsChainGreeksEstimator``)
without embedding QuantLib or other engines inside vendor implementations.
"""

from datetime import datetime
from typing import Any

from copinanceos.domain.models.market import MarketDataPoint, OptionsChain
from copinanceos.domain.ports.analytics import OptionsChainGreeksEstimator
from copinanceos.domain.ports.data_providers import MarketDataProvider


class OptionAnalyticsMarketDataProvider(MarketDataProvider):
    """Delegates to a source provider and runs ``OptionsChainGreeksEstimator`` on options chains."""

    def __init__(
        self,
        inner: MarketDataProvider,
        option_greeks_estimator: OptionsChainGreeksEstimator,
    ) -> None:
        self._inner = inner
        self._option_greeks_estimator = option_greeks_estimator

    async def is_available(self) -> bool:
        return await self._inner.is_available()

    def get_provider_name(self) -> str:
        return self._inner.get_provider_name()

    async def get_quote(self, symbol: str) -> dict[str, Any]:
        return await self._inner.get_quote(symbol)

    async def get_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
    ) -> list[MarketDataPoint]:
        return await self._inner.get_historical_data(
            symbol, start_date, end_date, interval=interval
        )

    async def get_intraday_data(
        self,
        symbol: str,
        interval: str = "1min",
    ) -> list[MarketDataPoint]:
        return await self._inner.get_intraday_data(symbol, interval=interval)

    async def search_instruments(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        return await self._inner.search_instruments(query, limit=limit)

    async def get_options_chain(
        self,
        underlying_symbol: str,
        expiration_date: str | None = None,
    ) -> OptionsChain:
        raw_chain = await self._inner.get_options_chain(
            underlying_symbol=underlying_symbol,
            expiration_date=expiration_date,
        )
        return self._option_greeks_estimator.estimate(raw_chain)
