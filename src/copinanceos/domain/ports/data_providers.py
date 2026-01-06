"""Data ingestion and integration layer interfaces."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from copinanceos.domain.models.fundamentals import StockFundamentals
from copinanceos.domain.models.macro import MacroDataPoint
from copinanceos.domain.models.stock import StockData


class DataProvider(ABC):
    """Base interface for data providers."""

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the data provider is available."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the name of the data provider."""
        pass


class MarketDataProvider(DataProvider):
    """Interface for market data providers (Bloomberg, Refinitiv, Alpha Vantage, Polygon)."""

    @abstractmethod
    async def get_quote(self, symbol: str) -> dict[str, Any]:
        """Get current quote for a symbol."""
        pass

    @abstractmethod
    async def get_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
    ) -> list[StockData]:
        """Get historical market data."""
        pass

    @abstractmethod
    async def get_intraday_data(
        self,
        symbol: str,
        interval: str = "1min",
    ) -> list[StockData]:
        """Get intraday market data."""
        pass

    @abstractmethod
    async def search_stocks(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search for stocks by symbol or company name.

        Args:
            query: Search query (can be symbol or company name)
            limit: Maximum number of results to return

        Returns:
            List of stock search results with symbol, name, exchange, etc.
        """
        pass


class AlternativeDataProvider(DataProvider):
    """Interface for alternative data sources."""

    @abstractmethod
    async def get_sentiment_data(
        self,
        symbol: str,
        sources: list[str],
        lookback_days: int = 30,
    ) -> dict[str, Any]:
        """
        Get sentiment data from social media and news.

        Sources: Twitter, Reddit, StockTwits, news articles
        """
        pass

    @abstractmethod
    async def get_web_traffic_metrics(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Get web traffic and app metrics (SimilarWeb, App Store)."""
        pass

    @abstractmethod
    async def get_satellite_imagery_insights(
        self,
        symbol: str,
        locations: list[str],
    ) -> dict[str, Any]:
        """Get satellite imagery insights (Orbital Insight) for retail/logistics."""
        pass

    @abstractmethod
    async def get_supply_chain_data(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """Get supply chain data (Panjiva, ImportGenius)."""
        pass

    @abstractmethod
    async def get_transaction_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Get credit card transaction aggregates (Second Measure)."""
        pass


class FundamentalDataProvider(DataProvider):
    """Interface for fundamental data providers."""

    @abstractmethod
    async def get_financial_statements(
        self,
        symbol: str,
        statement_type: str,
        period: str = "annual",
    ) -> dict[str, Any]:
        """
        Get financial statements.

        statement_type: income_statement, balance_sheet, cash_flow
        period: annual, quarterly
        """
        pass

    @abstractmethod
    async def get_sec_filings(
        self,
        symbol: str,
        filing_types: list[str],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get SEC filings from EDGAR (10-K, 10-Q, 8-K, etc.)."""
        pass

    @abstractmethod
    async def get_earnings_transcripts(
        self,
        symbol: str,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        """Get earnings call transcripts."""
        pass

    @abstractmethod
    async def get_esg_metrics(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """Get ESG metrics (Sustainalytics, MSCI)."""
        pass

    @abstractmethod
    async def get_insider_trading(
        self,
        symbol: str,
        lookback_days: int = 90,
    ) -> list[dict[str, Any]]:
        """Get insider trading activity."""
        pass

    @abstractmethod
    async def get_detailed_fundamentals(
        self,
        symbol: str,
        periods: int = 5,
        period_type: str = "annual",
    ) -> StockFundamentals:
        """
        Get comprehensive detailed fundamentals for a stock.

        This method aggregates financial statements, calculates ratios, and provides
        a complete fundamental analysis view. The implementation is provider-agnostic
        and should normalize data from any source into the StockFundamentals model.

        Args:
            symbol: Stock ticker symbol
            periods: Number of periods to retrieve (e.g., 5 years of annual data)
            period_type: "annual" or "quarterly"

        Returns:
            StockFundamentals entity with comprehensive fundamental data
        """
        pass


class MacroeconomicDataProvider(DataProvider):
    """Interface for macroeconomic time-series data providers (e.g., FRED)."""

    @abstractmethod
    async def get_time_series(
        self,
        series_id: str,
        start_date: datetime,
        end_date: datetime,
        *,
        frequency: str | None = None,
    ) -> list[MacroDataPoint]:
        """Get a macroeconomic time series as ordered date/value points.

        Args:
            series_id: Provider-specific series identifier (e.g., FRED series id like "DGS10")
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            frequency: Optional provider-specific frequency override (e.g., "d", "w", "m")

        Returns:
            Ordered list of MacroDataPoint values. Missing/invalid points may be omitted.
        """
        raise NotImplementedError
