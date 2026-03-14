"""Market instrument use cases."""

import asyncio
from decimal import Decimal
from enum import StrEnum

import structlog
from pydantic import BaseModel, Field

from copinanceos.application.use_cases.base import UseCase
from copinanceos.domain.models.market import MarketDataPoint
from copinanceos.domain.models.stock import Stock
from copinanceos.domain.ports.data_providers import MarketDataProvider
from copinanceos.domain.ports.repositories import StockRepository
from copinanceos.domain.validation import StockSymbolValidator

logger = structlog.get_logger(__name__)


class InstrumentSearchMode(StrEnum):
    """Search mode for instrument lookup."""

    AUTO = "auto"
    SYMBOL = "symbol"
    GENERAL = "general"


class GetInstrumentRequest(BaseModel):
    """Request to get equity instrument information."""

    symbol: str = Field(..., description="Instrument symbol")


class GetInstrumentResponse(BaseModel):
    """Response from getting instrument information."""

    instrument: Stock | None = Field(..., description="Instrument entity if found")


class GetInstrumentUseCase(UseCase[GetInstrumentRequest, GetInstrumentResponse]):
    """Use case for retrieving cached equity instrument information."""

    def __init__(self, instrument_repository: StockRepository) -> None:
        self._instrument_repository = instrument_repository

    async def execute(self, request: GetInstrumentRequest) -> GetInstrumentResponse:
        instrument = await self._instrument_repository.get_by_symbol(request.symbol)
        return GetInstrumentResponse(instrument=instrument)


class SearchInstrumentsRequest(BaseModel):
    """Request to search market instruments."""

    query: str = Field(..., description="Search query")
    limit: int = Field(default=10, description="Maximum results to return")
    search_mode: InstrumentSearchMode = Field(
        default=InstrumentSearchMode.AUTO,
        description="Search mode: auto, symbol, or general",
    )


class SearchInstrumentsResponse(BaseModel):
    """Response from searching market instruments."""

    instruments: list[Stock] = Field(default_factory=list, description="Matching instruments")


class SearchInstrumentsUseCase(UseCase[SearchInstrumentsRequest, SearchInstrumentsResponse]):
    """Use case for searching market instruments."""

    def __init__(
        self,
        instrument_repository: StockRepository,
        market_data_provider: MarketDataProvider | None = None,
    ) -> None:
        self._instrument_repository = instrument_repository
        self._market_data_provider = market_data_provider

    async def _fetch_instrument_from_provider(self, symbol: str) -> Stock | None:
        if not self._market_data_provider:
            return None

        try:
            if not await self._market_data_provider.is_available():
                logger.debug("Market data provider not available", symbol=symbol)
                return None

            quote = await self._market_data_provider.get_quote(symbol.upper())

            try:
                import yfinance as yf  # type: ignore[import-untyped]  # noqa: PLC0415

                loop = asyncio.get_event_loop()
                ticker = await loop.run_in_executor(None, lambda: yf.Ticker(symbol.upper()))
                info = await loop.run_in_executor(None, lambda: ticker.info)

                if not info or not isinstance(info, dict):
                    logger.warning("Invalid symbol or no data from yfinance", symbol=symbol)
                    return None

                instrument_name = info.get("longName") or info.get("shortName")
                if not instrument_name:
                    logger.warning("No instrument name found for symbol", symbol=symbol)
                    return None

                instrument = Stock(
                    symbol=symbol.upper(),
                    name=instrument_name,
                    exchange=info.get("exchange", quote.get("exchange", "")),
                    sector=info.get("sector"),
                    industry=info.get("industry"),
                    market_cap=(
                        Decimal(str(info.get("marketCap", 0))) if info.get("marketCap") else None
                    ),
                    website=info.get("website"),
                    country=info.get("country"),
                    currency=info.get("currency"),
                    phone=info.get("phone"),
                    city=info.get("city"),
                    state=info.get("state"),
                    enterprise_value=(
                        Decimal(str(info.get("enterpriseValue", 0)))
                        if info.get("enterpriseValue")
                        else None
                    ),
                    shares_outstanding=(
                        int(info.get("sharesOutstanding", 0))
                        if info.get("sharesOutstanding")
                        else None
                    ),
                    float_shares=(
                        int(info.get("floatShares", 0)) if info.get("floatShares") else None
                    ),
                    beta=(
                        Decimal(str(info.get("beta", 0))) if info.get("beta") is not None else None
                    ),
                    dividend_yield=(
                        Decimal(str(info.get("dividendYield", 0)))
                        if info.get("dividendYield") is not None
                        else None
                    ),
                    employees=(
                        int(info.get("fullTimeEmployees", 0))
                        if info.get("fullTimeEmployees")
                        else None
                    ),
                    data_provider="yfinance",
                )

                await self._instrument_repository.save(instrument)
                logger.info("Fetched and saved instrument from provider", symbol=symbol)
                return instrument

            except ImportError:
                if quote.get("exchange"):
                    instrument = Stock(
                        symbol=symbol.upper(),
                        name=quote.get("symbol", symbol.upper()),
                        exchange=quote.get("exchange", ""),
                        sector=None,
                        industry=None,
                        market_cap=None,
                        website=None,
                        country=None,
                        currency=None,
                        phone=None,
                        city=None,
                        state=None,
                        enterprise_value=None,
                        shares_outstanding=None,
                        float_shares=None,
                        beta=None,
                        dividend_yield=None,
                        employees=None,
                        data_provider="quote",
                    )
                    await self._instrument_repository.save(instrument)
                    return instrument
                return None
            except Exception as provider_error:
                logger.warning(
                    "Failed to fetch instrument info from yfinance",
                    symbol=symbol,
                    error=str(provider_error),
                )
                return None

        except Exception as e:
            logger.warning("Failed to fetch instrument from provider", symbol=symbol, error=str(e))
            return None

    async def execute(self, request: SearchInstrumentsRequest) -> SearchInstrumentsResponse:
        instruments = await self._instrument_repository.search(request.query, request.limit)

        if not instruments and self._market_data_provider:
            use_symbol_search = False
            use_general_search = False

            if request.search_mode == InstrumentSearchMode.SYMBOL:
                use_symbol_search = True
            elif request.search_mode == InstrumentSearchMode.GENERAL:
                use_general_search = True
            else:
                if StockSymbolValidator.looks_like_symbol(request.query):
                    use_symbol_search = True
                else:
                    use_general_search = True

            if use_symbol_search:
                fetched_instrument = await self._fetch_instrument_from_provider(
                    request.query.upper()
                )
                if fetched_instrument:
                    instruments = [fetched_instrument]
            elif use_general_search:
                search_results = await self._market_data_provider.search_instruments(
                    request.query, limit=request.limit
                )
                for result in search_results:
                    symbol = result.get("symbol", "")
                    if symbol:
                        fetched_instrument = await self._fetch_instrument_from_provider(symbol)
                        if fetched_instrument:
                            instruments.append(fetched_instrument)
                            if len(instruments) >= request.limit:
                                break

        return SearchInstrumentsResponse(instruments=instruments)


class GetMarketDataRequest(BaseModel):
    """Request to get historical instrument market data."""

    symbol: str = Field(..., description="Instrument symbol")
    limit: int = Field(default=100, description="Number of data points to retrieve")


class GetMarketDataResponse(BaseModel):
    """Response from getting historical market data."""

    data: list[MarketDataPoint] = Field(
        default_factory=list,
        description="Historical market data",
    )


class GetMarketDataUseCase(UseCase[GetMarketDataRequest, GetMarketDataResponse]):
    """Use case for retrieving cached historical market data."""

    def __init__(self, instrument_repository: StockRepository) -> None:
        self._instrument_repository = instrument_repository

    async def execute(self, request: GetMarketDataRequest) -> GetMarketDataResponse:
        data = await self._instrument_repository.get_market_data(request.symbol, request.limit)
        return GetMarketDataResponse(data=data)
