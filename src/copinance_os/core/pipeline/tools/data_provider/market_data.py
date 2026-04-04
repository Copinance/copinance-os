"""Market data provider tools."""

import asyncio
from datetime import datetime
from typing import Any

import structlog

from copinance_os.core.pipeline.tools.data_provider.base import BaseDataProviderTool
from copinance_os.data.cache import CacheManager
from copinance_os.domain.models.analysis import merge_instrument_expiration_inputs
from copinance_os.domain.models.market import OptionSide
from copinance_os.domain.models.tool_results import ToolResult
from copinance_os.domain.ports.data_providers import MarketDataProvider
from copinance_os.domain.ports.tools import ToolSchema
from copinance_os.infra.error_handler import flatten_exception_message

logger = structlog.get_logger(__name__)


class MarketDataGetQuoteTool(BaseDataProviderTool[MarketDataProvider]):
    """Tool for getting a current market quote."""

    def __init__(
        self,
        provider: MarketDataProvider,
        cache_manager: CacheManager | None = None,
        use_cache: bool = True,
    ) -> None:
        super().__init__(provider, cache_manager=cache_manager, use_cache=use_cache)

    def get_name(self) -> str:
        return "get_market_quote"

    def get_description(self) -> str:
        return "Get the current quote for a market instrument."

    def get_schema(self) -> ToolSchema:
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Instrument symbol (e.g., 'AAPL', 'MSFT', 'SPY')",
                    }
                },
                "required": ["symbol"],
            },
            returns={
                "type": "object",
                "description": "Instrument quote with price, volume, and reference market data",
            },
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        try:
            validated = self.validate_parameters(**kwargs)
            symbol = validated["symbol"]
            quote = await self._provider.get_quote(symbol)
            return self._create_success_result(data=quote, metadata={"symbol": symbol})
        except Exception as e:
            logger.error("Failed to get market quote", error=str(e), symbol=kwargs.get("symbol"))
            return self._create_error_result(error=e, metadata={"symbol": kwargs.get("symbol")})


class MarketDataGetHistoricalDataTool(BaseDataProviderTool[MarketDataProvider]):
    """Tool for getting historical market data."""

    def __init__(
        self,
        provider: MarketDataProvider,
        cache_manager: CacheManager | None = None,
        use_cache: bool = True,
    ) -> None:
        super().__init__(provider, cache_manager=cache_manager, use_cache=use_cache)

    def get_name(self) -> str:
        return "get_historical_market_data"

    def get_description(self) -> str:
        return "Get historical OHLCV market data for a symbol and date range."

    def get_schema(self) -> ToolSchema:
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Instrument symbol (e.g., 'AAPL', 'SPY')",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date in ISO format (YYYY-MM-DD)",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date in ISO format (YYYY-MM-DD)",
                    },
                    "interval": {
                        "type": "string",
                        "description": "Data interval",
                        "enum": ["1d", "1wk", "1mo", "1h", "5m", "15m", "30m", "60m"],
                        "default": "1d",
                    },
                },
                "required": ["symbol", "start_date", "end_date"],
            },
            returns={
                "type": "array",
                "description": "Array of historical market data points",
            },
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        try:
            validated = self.validate_parameters(**kwargs)
            symbol = validated["symbol"]
            start_date = datetime.fromisoformat(validated["start_date"])
            end_date = datetime.fromisoformat(validated["end_date"])
            interval = validated.get("interval", "1d")
            historical_data = await self._provider.get_historical_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval=interval,
            )
            data = self._serialize_data(historical_data)
            return self._create_success_result(
                data=data,
                metadata={
                    "symbol": symbol,
                    "start_date": validated["start_date"],
                    "end_date": validated["end_date"],
                    "interval": interval,
                    "data_points": len(data),
                },
            )
        except Exception as e:
            logger.error(
                "Failed to get historical market data",
                error=str(e),
                symbol=kwargs.get("symbol"),
            )
            return self._create_error_result(error=e, metadata={"symbol": kwargs.get("symbol")})


class MarketDataSearchInstrumentsTool(BaseDataProviderTool[MarketDataProvider]):
    """Tool for searching market instruments."""

    def __init__(
        self,
        provider: MarketDataProvider,
        cache_manager: CacheManager | None = None,
        use_cache: bool = True,
    ) -> None:
        super().__init__(provider, cache_manager=cache_manager, use_cache=use_cache)

    def get_name(self) -> str:
        return "search_market_instruments"

    def get_description(self) -> str:
        return "Search market instruments by symbol or name."

    def get_schema(self) -> ToolSchema:
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (symbol or display name)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 10,
                    },
                },
                "required": ["query"],
            },
            returns={
                "type": "array",
                "description": "List of matching instruments with symbol, name, exchange, etc.",
            },
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        try:
            validated = self.validate_parameters(**kwargs)
            query = validated["query"]
            limit = validated.get("limit", 10)
            results = await self._provider.search_instruments(query=query, limit=limit)
            return self._create_success_result(
                data=results,
                metadata={"query": query, "limit": limit, "results_count": len(results)},
            )
        except Exception as e:
            logger.error(
                "Failed to search market instruments",
                error=str(e),
                query=kwargs.get("query"),
            )
            return self._create_error_result(error=e, metadata={"query": kwargs.get("query")})


class MarketDataGetOptionsChainTool(BaseDataProviderTool[MarketDataProvider]):
    """Tool for getting an options chain."""

    def __init__(
        self,
        provider: MarketDataProvider,
        cache_manager: CacheManager | None = None,
        use_cache: bool = True,
    ) -> None:
        super().__init__(provider, cache_manager=cache_manager, use_cache=use_cache)

    def get_name(self) -> str:
        return "get_options_chain"

    def get_description(self) -> str:
        return (
            "Get options chain(s) for an underlying instrument. "
            "Pass expiration_date for one expiry, expiration_dates for several, "
            "or omit both to use the provider default expiry."
        )

    def validate_parameters(self, **kwargs: Any) -> dict[str, Any]:
        """Normalize optional params so nulls do not fail string/array validation."""
        kw = dict(kwargs)
        if kw.get("expiration_dates") is None:
            kw.pop("expiration_dates", None)
        if kw.get("expiration_date") is None:
            kw.pop("expiration_date", None)
        return super().validate_parameters(**kw)

    def get_schema(self) -> ToolSchema:
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "underlying_symbol": {
                        "type": "string",
                        "description": "Underlying instrument symbol (e.g., 'AAPL', 'SPY')",
                    },
                    "expiration_date": {
                        "type": "string",
                        "description": (
                            "Optional single expiration in YYYY-MM-DD. "
                            "Merged with expiration_dates if both are set (deduplicated)."
                        ),
                    },
                    "expiration_dates": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional list of expirations in YYYY-MM-DD. "
                            "Use this to fetch multiple chains in one call. "
                            "Merged with expiration_date when both are set."
                        ),
                    },
                    "option_side": {
                        "type": "string",
                        "description": "Optional side filter",
                        "enum": [OptionSide.CALL.value, OptionSide.PUT.value, OptionSide.ALL.value],
                        "default": OptionSide.ALL.value,
                    },
                },
                "required": ["underlying_symbol"],
            },
            returns={
                "type": "object",
                "description": (
                    "Single chain: calls, puts, expirations, underlying price. "
                    "Multiple expirations: multi_expiration=true with expirations array of chains."
                ),
            },
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    @staticmethod
    def _apply_option_side_filter(data: dict[str, Any], option_side: OptionSide) -> dict[str, Any]:
        out = dict(data)
        if option_side == OptionSide.CALL:
            out["puts"] = []
        elif option_side == OptionSide.PUT:
            out["calls"] = []
        return out

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        try:
            validated = self.validate_parameters(**kwargs)
            underlying_symbol = validated["underlying_symbol"]
            option_side = OptionSide(validated.get("option_side", OptionSide.ALL.value))
            eds = validated.get("expiration_dates")
            if eds is not None:
                for i, x in enumerate(eds):
                    if not isinstance(x, str):
                        return self._create_error_result(
                            error=ValueError(
                                f"expiration_dates[{i}] must be a string (YYYY-MM-DD)"
                            ),
                            metadata={"underlying_symbol": underlying_symbol},
                        )
            try:
                merged = merge_instrument_expiration_inputs(
                    validated.get("expiration_date"),
                    validated.get("expiration_dates"),
                )
            except ValueError as e:
                return self._create_error_result(
                    error=e,
                    metadata={"underlying_symbol": underlying_symbol},
                )

            if len(merged) <= 1:
                exp = merged[0] if merged else None
                options_chain = await self._provider.get_options_chain(
                    underlying_symbol=underlying_symbol,
                    expiration_date=exp,
                )
                data = self._serialize_data(options_chain)
                data = self._apply_option_side_filter(data, option_side)
                return self._create_success_result(
                    data=data,
                    metadata={
                        "underlying_symbol": underlying_symbol,
                        "expiration_date": exp,
                        "expiration_dates": merged if merged else None,
                        "option_side": option_side.value,
                    },
                )

            async def _one_expiry(exp: str) -> dict[str, Any]:
                chain = await self._provider.get_options_chain(
                    underlying_symbol=underlying_symbol,
                    expiration_date=exp,
                )
                ser = self._serialize_data(chain)
                return self._apply_option_side_filter(ser, option_side)

            async with asyncio.TaskGroup() as tg:
                tasks = [tg.create_task(_one_expiry(d)) for d in merged]
            expirations = [t.result() for t in tasks]

            return self._create_success_result(
                data={
                    "multi_expiration": True,
                    "underlying_symbol": underlying_symbol,
                    "expirations": expirations,
                },
                metadata={
                    "underlying_symbol": underlying_symbol,
                    "expiration_date": None,
                    "expiration_dates": merged,
                    "option_side": option_side.value,
                },
            )
        except Exception as e:
            display_error = (
                flatten_exception_message(e) if isinstance(e, BaseExceptionGroup) else str(e)
            )
            logger.error(
                "Failed to get options chain",
                error=display_error,
                underlying_symbol=kwargs.get("underlying_symbol"),
                exc_info=True,
            )
            wrapped: Exception = (
                RuntimeError(display_error) if isinstance(e, BaseExceptionGroup) else e
            )
            return self._create_error_result(
                error=wrapped,
                metadata={"underlying_symbol": kwargs.get("underlying_symbol")},
            )
