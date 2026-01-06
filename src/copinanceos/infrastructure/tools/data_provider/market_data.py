"""Market data provider tools."""

from datetime import datetime
from typing import Any

import structlog

from copinanceos.domain.models.tool_results import ToolResult
from copinanceos.domain.ports.data_providers import MarketDataProvider
from copinanceos.domain.ports.tools import ToolSchema
from copinanceos.infrastructure.cache import CacheManager
from copinanceos.infrastructure.tools.data_provider.base import BaseDataProviderTool

logger = structlog.get_logger(__name__)


class MarketDataGetQuoteTool(BaseDataProviderTool[MarketDataProvider]):
    """Tool for getting current stock quote."""

    def __init__(
        self,
        provider: MarketDataProvider,
        cache_manager: CacheManager | None = None,
        use_cache: bool = True,
    ) -> None:
        """Initialize tool with market data provider.

        Args:
            provider: Market data provider instance
            cache_manager: Optional cache manager for caching tool results
            use_cache: Whether to use caching (default: True if cache_manager is provided)
        """
        super().__init__(provider, cache_manager=cache_manager, use_cache=use_cache)

    def get_name(self) -> str:
        """Get tool name."""
        return "get_stock_quote"

    def get_description(self) -> str:
        """Get tool description."""
        return "Get current stock quote including price, volume, and market data for a given stock symbol."

    def get_schema(self) -> ToolSchema:
        """Get tool schema."""
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol (e.g., 'AAPL', 'MSFT')",
                    }
                },
                "required": ["symbol"],
            },
            returns={
                "type": "object",
                "description": "Stock quote with price, volume, and other market data",
            },
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        """Execute tool to get stock quote."""
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        """Execute tool implementation."""
        try:
            validated = self.validate_parameters(**kwargs)
            symbol = validated["symbol"]

            quote = await self._provider.get_quote(symbol)

            return self._create_success_result(
                data=quote,
                metadata={"symbol": symbol},
            )
        except Exception as e:
            logger.error("Failed to get stock quote", error=str(e), symbol=kwargs.get("symbol"))
            return self._create_error_result(
                error=e,
                metadata={"symbol": kwargs.get("symbol")},
            )


class MarketDataGetHistoricalDataTool(BaseDataProviderTool[MarketDataProvider]):
    """Tool for getting historical stock data."""

    def __init__(
        self,
        provider: MarketDataProvider,
        cache_manager: CacheManager | None = None,
        use_cache: bool = True,
    ) -> None:
        """Initialize tool with market data provider.

        Args:
            provider: Market data provider instance
            cache_manager: Optional cache manager for caching tool results
            use_cache: Whether to use caching (default: True if cache_manager is provided)
        """
        super().__init__(provider, cache_manager=cache_manager, use_cache=use_cache)

    def get_name(self) -> str:
        """Get tool name."""
        return "get_historical_stock_data"

    def get_description(self) -> str:
        """Get tool description."""
        return "Get historical stock price data (OHLCV) for a given symbol and date range."

    def get_schema(self) -> ToolSchema:
        """Get tool schema."""
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol (e.g., 'AAPL', 'MSFT')",
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
                        "description": "Data interval (1d, 1wk, 1mo, etc.)",
                        "enum": ["1d", "1wk", "1mo", "1h", "5m", "15m", "30m", "60m"],
                        "default": "1d",
                    },
                },
                "required": ["symbol", "start_date", "end_date"],
            },
            returns={
                "type": "array",
                "description": "Array of historical stock data points",
            },
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        """Execute tool to get historical data."""
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        """Execute tool implementation."""
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

            # Convert to serializable format
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
                "Failed to get historical data",
                error=str(e),
                symbol=kwargs.get("symbol"),
            )
            return self._create_error_result(
                error=e,
                metadata={"symbol": kwargs.get("symbol")},
            )


class MarketDataSearchStocksTool(BaseDataProviderTool[MarketDataProvider]):
    """Tool for searching stocks."""

    def __init__(
        self,
        provider: MarketDataProvider,
        cache_manager: CacheManager | None = None,
        use_cache: bool = True,
    ) -> None:
        """Initialize tool with market data provider.

        Args:
            provider: Market data provider instance
            cache_manager: Optional cache manager for caching tool results
            use_cache: Whether to use caching (default: True if cache_manager is provided)
        """
        super().__init__(provider, cache_manager=cache_manager, use_cache=use_cache)

    def get_name(self) -> str:
        """Get tool name."""
        return "search_stocks"

    def get_description(self) -> str:
        """Get tool description."""
        return "Search for stocks by symbol or company name."

    def get_schema(self) -> ToolSchema:
        """Get tool schema."""
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (symbol or company name)",
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
                "description": "List of matching stocks with symbol, name, exchange, etc.",
            },
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        """Execute tool to search stocks."""
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        """Execute tool implementation."""
        try:
            validated = self.validate_parameters(**kwargs)
            query = validated["query"]
            limit = validated.get("limit", 10)

            results = await self._provider.search_stocks(query=query, limit=limit)

            return self._create_success_result(
                data=results,
                metadata={
                    "query": query,
                    "limit": limit,
                    "results_count": len(results),
                },
            )
        except Exception as e:
            logger.error("Failed to search stocks", error=str(e), query=kwargs.get("query"))
            return self._create_error_result(
                error=e,
                metadata={"query": kwargs.get("query")},
            )
