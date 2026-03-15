"""Market use cases: search, instrument, quote, historical data, options chain."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

import structlog
from pydantic import BaseModel, Field

from copinanceos.application.use_cases.base import UseCase
from copinanceos.domain.models.market import MarketDataPoint, OptionsChain
from copinanceos.domain.models.stock import Stock
from copinanceos.domain.ports.data_providers import MarketDataProvider
from copinanceos.domain.ports.repositories import StockRepository
from copinanceos.domain.validation import StockSymbolValidator

logger = structlog.get_logger(__name__)


def _is_stub_instrument(stock: Stock) -> bool:
    """True if this looks like a stub (e.g. from failed or partial symbol resolution)."""
    return (
        not (stock.exchange or "").strip()
        and (stock.name or "").strip().upper() == (stock.symbol or "").strip().upper()
    )


def _stock_from_quote(symbol: str, quote: dict[str, Any]) -> Stock:
    """Build a Stock from a provider quote dict (provider-agnostic)."""
    name = (
        quote.get("longName")
        or quote.get("shortName")
        or quote.get("name")
        or quote.get("symbol", symbol)
    )
    if isinstance(name, str):
        name = name.strip() or symbol.upper()
    else:
        name = symbol.upper()

    def _dec(v: Any) -> Decimal | None:
        if v is None:
            return None
        try:
            return Decimal(str(v))
        except (ValueError, TypeError):
            return None

    def _int(v: Any) -> int | None:
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    return Stock(
        symbol=(quote.get("symbol") or symbol).upper(),
        name=name,
        exchange=str(quote.get("exchange", "") or ""),
        sector=quote.get("sector"),
        industry=quote.get("industry"),
        market_cap=_dec(quote.get("market_cap")),
        website=quote.get("website"),
        country=quote.get("country"),
        currency=quote.get("currency"),
        phone=quote.get("phone"),
        city=quote.get("city"),
        state=quote.get("state"),
        enterprise_value=_dec(quote.get("enterprise_value")),
        shares_outstanding=_int(quote.get("sharesOutstanding") or quote.get("shares_outstanding")),
        float_shares=_int(quote.get("floatShares") or quote.get("float_shares")),
        beta=_dec(quote.get("beta")),
        dividend_yield=_dec(quote.get("dividendYield") or quote.get("dividend_yield")),
        employees=_int(quote.get("fullTimeEmployees") or quote.get("employees")),
        data_provider=quote.get("data_provider"),
    )


# ---- Search ----


class InstrumentSearchMode(StrEnum):
    """Search mode for instrument lookup."""

    AUTO = "auto"
    SYMBOL = "symbol"
    GENERAL = "general"


class SearchInstrumentsRequest(BaseModel):
    """Request to search market instruments by name or symbol."""

    query: str = Field(..., description="Search query (symbol or company name)")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum results to return")
    search_mode: InstrumentSearchMode = Field(
        default=InstrumentSearchMode.AUTO,
        description="Search mode: auto, symbol, or general",
    )


class SearchInstrumentsResponse(BaseModel):
    """Response from searching market instruments."""

    instruments: list[Stock] = Field(default_factory=list, description="Matching instruments")


class SearchInstrumentsUseCase(UseCase[SearchInstrumentsRequest, SearchInstrumentsResponse]):
    """Search market instruments by symbol or name; uses repository cache and live provider."""

    def __init__(
        self,
        instrument_repository: StockRepository,
        market_data_provider: MarketDataProvider | None = None,
    ) -> None:
        self._instrument_repository = instrument_repository
        self._market_data_provider = market_data_provider

    async def _resolve_instrument_from_provider(self, symbol: str) -> Stock | None:
        if not self._market_data_provider:
            return None
        try:
            if not await self._market_data_provider.is_available():
                logger.debug("Market data provider not available", symbol=symbol)
                return None
            quote = await self._market_data_provider.get_quote(symbol.upper())
            if not quote or not quote.get("symbol"):
                return None
            instrument = _stock_from_quote(symbol.upper(), quote)
            await self._instrument_repository.save(instrument)
            logger.info("Resolved and saved instrument from provider", symbol=symbol)
            return instrument
        except Exception as e:
            logger.warning(
                "Failed to resolve instrument from provider", symbol=symbol, error=str(e)
            )
            return None

    async def execute(self, request: SearchInstrumentsRequest) -> SearchInstrumentsResponse:
        instruments = await self._instrument_repository.search(request.query, request.limit)
        # If the only cache hits are stubs (e.g. bad symbol "APPLE" saved earlier), treat as empty
        # so the provider can return real results (e.g. AAPL for "APPLE").
        if instruments and all(_is_stub_instrument(s) for s in instruments):
            instruments = []

        if not instruments and self._market_data_provider:
            use_symbol = False
            if request.search_mode == InstrumentSearchMode.SYMBOL:
                use_symbol = True
            elif request.search_mode == InstrumentSearchMode.GENERAL:
                use_symbol = False
            else:
                use_symbol = StockSymbolValidator.looks_like_symbol(request.query)

            if use_symbol:
                one = await self._resolve_instrument_from_provider(request.query.upper())
                if one:
                    instruments = [one]
                # Symbol lookup failed (e.g. "APPLE" is not a ticker); fall back to name search
                # so "APPLE" returns AAPL via yfinance Search.
                if not instruments:
                    raw = await self._market_data_provider.search_instruments(
                        request.query, limit=request.limit
                    )
                    for item in raw:
                        sym = (item.get("symbol") or "").strip()
                        if not sym:
                            continue
                        one = await self._resolve_instrument_from_provider(sym)
                        if one:
                            instruments.append(one)
                            if len(instruments) >= request.limit:
                                break
            else:
                raw = await self._market_data_provider.search_instruments(
                    request.query, limit=request.limit
                )
                for item in raw:
                    sym = (item.get("symbol") or "").strip()
                    if not sym:
                        continue
                    one = await self._resolve_instrument_from_provider(sym)
                    if one:
                        instruments.append(one)
                        if len(instruments) >= request.limit:
                            break

        return SearchInstrumentsResponse(instruments=instruments)


# ---- Get instrument (cached) ----


class GetInstrumentRequest(BaseModel):
    """Request to get equity instrument information by symbol."""

    symbol: str = Field(..., description="Instrument symbol")


class GetInstrumentResponse(BaseModel):
    """Response from getting instrument information."""

    instrument: Stock | None = Field(..., description="Instrument if found")


class GetInstrumentUseCase(UseCase[GetInstrumentRequest, GetInstrumentResponse]):
    """Get cached equity instrument by symbol."""

    def __init__(self, instrument_repository: StockRepository) -> None:
        self._instrument_repository = instrument_repository

    async def execute(self, request: GetInstrumentRequest) -> GetInstrumentResponse:
        instrument = await self._instrument_repository.get_by_symbol(request.symbol)
        return GetInstrumentResponse(instrument=instrument)


# ---- Get quote ----


class GetQuoteRequest(BaseModel):
    """Request to get current market quote for a symbol."""

    symbol: str = Field(..., description="Instrument symbol")


class GetQuoteResponse(BaseModel):
    """Response with current quote data."""

    quote: dict[str, Any] = Field(default_factory=dict, description="Quote payload from provider")
    symbol: str = Field(..., description="Instrument symbol")


class GetQuoteUseCase(UseCase[GetQuoteRequest, GetQuoteResponse]):
    """Get current market quote for a symbol from the market data provider."""

    def __init__(self, market_data_provider: MarketDataProvider) -> None:
        self._market_data_provider = market_data_provider

    async def execute(self, request: GetQuoteRequest) -> GetQuoteResponse:
        symbol = request.symbol.upper()
        quote = await self._market_data_provider.get_quote(symbol)
        quote = dict(quote) if quote else {}
        if "symbol" not in quote:
            quote["symbol"] = symbol
        return GetQuoteResponse(quote=quote, symbol=symbol)


# ---- Get historical data ----


class GetHistoricalDataRequest(BaseModel):
    """Request to get historical OHLCV data for a symbol."""

    symbol: str = Field(..., description="Instrument symbol")
    start_date: datetime = Field(..., description="Start date (inclusive)")
    end_date: datetime = Field(..., description="End date (inclusive)")
    interval: str = Field(default="1d", description="Bar interval (e.g. 1d, 1h, 5m)")


class GetHistoricalDataResponse(BaseModel):
    """Response with historical market data points."""

    data: list[MarketDataPoint] = Field(
        default_factory=list,
        description="Historical OHLCV data points",
    )
    symbol: str = Field(..., description="Instrument symbol")


class GetHistoricalDataUseCase(UseCase[GetHistoricalDataRequest, GetHistoricalDataResponse]):
    """Get historical market data for a symbol from the market data provider."""

    def __init__(self, market_data_provider: MarketDataProvider) -> None:
        self._market_data_provider = market_data_provider

    async def execute(self, request: GetHistoricalDataRequest) -> GetHistoricalDataResponse:
        symbol = request.symbol.upper()
        data = await self._market_data_provider.get_historical_data(
            symbol=symbol,
            start_date=request.start_date,
            end_date=request.end_date,
            interval=request.interval,
        )
        return GetHistoricalDataResponse(data=data, symbol=symbol)


# ---- Get options chain ----


class GetOptionsChainRequest(BaseModel):
    """Request to get options chain for an underlying symbol."""

    underlying_symbol: str = Field(..., description="Underlying instrument symbol")
    expiration_date: str | None = Field(
        None,
        description="Optional expiration date (YYYY-MM-DD); provider default if omitted",
    )


class GetOptionsChainResponse(BaseModel):
    """Response with options chain."""

    chain: OptionsChain = Field(..., description="Options chain for the underlying")
    underlying_symbol: str = Field(..., description="Underlying instrument symbol")


class GetOptionsChainUseCase(UseCase[GetOptionsChainRequest, GetOptionsChainResponse]):
    """Get options chain for an underlying symbol from the market data provider."""

    def __init__(self, market_data_provider: MarketDataProvider) -> None:
        self._market_data_provider = market_data_provider

    async def execute(self, request: GetOptionsChainRequest) -> GetOptionsChainResponse:
        underlying = request.underlying_symbol.upper()
        chain = await self._market_data_provider.get_options_chain(
            underlying_symbol=underlying,
            expiration_date=request.expiration_date,
        )
        return GetOptionsChainResponse(chain=chain, underlying_symbol=underlying)
