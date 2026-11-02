"""Fact-injection and null providers for pure computational engine execution.

In engine mode (default for library integration and host apps), copinance-os does not
reach out to Yahoo, FRED, SEC, or external networks. The embedding product or test
injects market facts directly using ``FactBasedMarketProvider`` or ``MarketFacts``.
If no provider is configured, calls fail closed with ``FactProviderNotConfigured``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from copinance_os.domain.models.market import MarketDataPoint, OptionsChain
from copinance_os.domain.models.market.fundamentals import StockFundamentals
from copinance_os.domain.models.market.macro import MacroDataPoint
from copinance_os.domain.ports.data_providers import (
    FundamentalDataProvider,
    MacroeconomicDataProvider,
    MarketDataProvider,
)


class FactProviderNotConfiguredError(RuntimeError):
    """Raised when copinance-os is used as an engine without an injected provider."""

    def __init__(self, operation: str) -> None:
        super().__init__(
            f"copinance-os is operating as an in-process computational engine. "
            f"No market data provider was configured for '{operation}'. "
            f"Inject a market_data_provider, supply MarketFacts, or pass standalone=True for CLI use."
        )


class FactNotFoundError(KeyError):
    """Raised when injected facts do not contain the requested instrument or series."""


FactProviderNotConfigured = FactProviderNotConfiguredError
FactNotFound = FactNotFoundError


@dataclass(frozen=True)
class MarketFacts:
    """Pre-fetched or caller-supplied facts for one symbol."""

    symbol: str
    quote: dict[str, Any] = field(default_factory=dict)
    historical_data: list[MarketDataPoint] = field(default_factory=list)
    intraday_data: list[MarketDataPoint] = field(default_factory=list)
    options_chain: OptionsChain | None = None
    search_results: list[dict[str, Any]] = field(default_factory=list)
    fundamentals: StockFundamentals | dict[str, Any] | None = None


class NullMarketDataProvider(MarketDataProvider):
    """Fail-closed provider: refuses any network requests in engine mode."""

    async def is_available(self) -> bool:
        return False

    def get_provider_name(self) -> str:
        return "engine_null"

    async def get_quote(self, symbol: str) -> dict[str, Any]:
        raise FactProviderNotConfigured(f"get_quote({symbol!r})")

    async def get_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
    ) -> list[MarketDataPoint]:
        raise FactProviderNotConfigured(f"get_historical_data({symbol!r})")

    async def get_intraday_data(
        self,
        symbol: str,
        interval: str = "1min",
    ) -> list[MarketDataPoint]:
        raise FactProviderNotConfigured(f"get_intraday_data({symbol!r})")

    async def search_instruments(
        self,
        query: str,
        limit: int = 10,
        quote_types: Sequence[str] | None = ("EQUITY", "ETF", ""),
    ) -> list[dict[str, Any]]:
        raise FactProviderNotConfigured(f"search_instruments({query!r})")

    async def get_options_chain(
        self,
        underlying_symbol: str,
        expiration_date: str | None = None,
    ) -> OptionsChain:
        raise FactProviderNotConfigured(f"get_options_chain({underlying_symbol!r})")


class NullFundamentalDataProvider(FundamentalDataProvider):
    """Fail-closed provider for fundamentals in engine mode."""

    async def is_available(self) -> bool:
        return False

    def get_provider_name(self) -> str:
        return "engine_null"

    async def get_financial_statements(
        self, symbol: str, statement_type: str, period: str = "annual"
    ) -> dict[str, Any]:
        raise FactProviderNotConfigured(f"get_financial_statements({symbol!r})")

    async def get_sec_filings(
        self, symbol: str, filing_types: list[str], limit: int = 10
    ) -> list[dict[str, Any]]:
        raise FactProviderNotConfigured(f"get_sec_filings({symbol!r})")

    async def get_earnings_transcripts(self, symbol: str, limit: int = 4) -> list[dict[str, Any]]:
        raise FactProviderNotConfigured(f"get_earnings_transcripts({symbol!r})")

    async def get_esg_metrics(self, symbol: str) -> dict[str, Any]:
        raise FactProviderNotConfigured(f"get_esg_metrics({symbol!r})")

    async def get_insider_trading(
        self, symbol: str, lookback_days: int = 90
    ) -> list[dict[str, Any]]:
        raise FactProviderNotConfigured(f"get_insider_trading({symbol!r})")

    async def get_detailed_fundamentals(
        self, symbol: str, periods: int = 5, period_type: str = "annual"
    ) -> StockFundamentals:
        raise FactProviderNotConfigured(f"get_detailed_fundamentals({symbol!r})")


class NullMacroDataProvider(MacroeconomicDataProvider):
    """Fail-closed provider for macro data in engine mode."""

    async def is_available(self) -> bool:
        return False

    def get_provider_name(self) -> str:
        return "engine_null"

    async def get_time_series(
        self,
        series_id: str,
        start_date: datetime,
        end_date: datetime,
        *,
        frequency: str | None = None,
    ) -> list[MacroDataPoint]:
        raise FactProviderNotConfigured(f"get_time_series({series_id!r})")


class FactBasedMarketProvider(MarketDataProvider):
    """Serves facts injected in-memory by host products or tests without network calls."""

    def __init__(
        self, facts: MarketFacts | Sequence[MarketFacts] | Mapping[str, MarketFacts]
    ) -> None:
        if isinstance(facts, MarketFacts):
            self._facts = {facts.symbol.upper(): facts}
        elif isinstance(facts, Mapping):
            self._facts = {k.upper(): v for k, v in facts.items()}
        else:
            self._facts = {f.symbol.upper(): f for f in facts}

    def _get(self, symbol: str) -> MarketFacts:
        key = symbol.strip().upper()
        if key not in self._facts:
            raise FactNotFound(f"No injected facts for symbol {symbol!r}")
        return self._facts[key]

    async def is_available(self) -> bool:
        return True

    def get_provider_name(self) -> str:
        return "fact_injection"

    async def get_quote(self, symbol: str) -> dict[str, Any]:
        facts = self._get(symbol)
        if not facts.quote:
            raise FactNotFound(f"No quote facts for symbol {symbol!r}")
        return facts.quote

    async def get_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
    ) -> list[MarketDataPoint]:
        facts = self._get(symbol)
        return [
            point for point in facts.historical_data if start_date <= point.timestamp <= end_date
        ]

    async def get_intraday_data(
        self,
        symbol: str,
        interval: str = "1min",
    ) -> list[MarketDataPoint]:
        facts = self._get(symbol)
        return list(facts.intraday_data)

    async def search_instruments(
        self,
        query: str,
        limit: int = 10,
        quote_types: Sequence[str] | None = ("EQUITY", "ETF", ""),
    ) -> list[dict[str, Any]]:
        q = query.strip().upper()
        results: list[dict[str, Any]] = []
        for symbol, fact in self._facts.items():
            if fact.search_results:
                results.extend(fact.search_results)
            elif q in symbol:
                results.append({"symbol": symbol, "name": fact.quote.get("name", symbol)})
        return results[:limit]

    async def get_options_chain(
        self,
        underlying_symbol: str,
        expiration_date: str | None = None,
    ) -> OptionsChain:
        facts = self._get(underlying_symbol)
        if facts.options_chain is None:
            raise FactNotFound(f"No options chain facts for symbol {underlying_symbol!r}")
        return facts.options_chain


class FactBasedMacroProvider(MacroeconomicDataProvider):
    """Serves macroeconomic facts injected in-memory without network calls."""

    def __init__(self, series: Mapping[str, list[MacroDataPoint]]) -> None:
        self._series = dict(series)

    async def is_available(self) -> bool:
        return True

    def get_provider_name(self) -> str:
        return "fact_injection_macro"

    async def get_time_series(
        self,
        series_id: str,
        start_date: datetime,
        end_date: datetime,
        *,
        frequency: str | None = None,
    ) -> list[MacroDataPoint]:
        points = self._series.get(series_id, [])
        return [p for p in points if start_date <= p.timestamp <= end_date]
