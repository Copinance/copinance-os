"""Market regime indicators tool.

This module provides tools for fetching comprehensive market regime indicators including:
- VIX (Volatility Index)
- Market Breadth (sector ETF analysis)
- Sector Rotation Signals

All data sources are free and use existing yfinance provider.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from copinanceos.domain.models.tool_results import ToolResult
from copinanceos.domain.ports.data_providers import MarketDataProvider
from copinanceos.domain.ports.tools import Tool, ToolSchema
from copinanceos.infrastructure.tools.analysis.market_regime.base import (
    _calculate_moving_average,
    _calculate_rsi,
)
from copinanceos.infrastructure.tools.analysis.market_regime.rule_based import (
    _calculate_volatility,
)

logger = structlog.get_logger(__name__)

# Sector ETF symbols for market breadth and rotation analysis
SECTOR_ETFS = {
    "XLK": "Technology",
    "XLE": "Energy",
    "XLI": "Industrial",
    "XLV": "Health Care",
    "XLF": "Financial",
    "XLP": "Consumer Staples",
    "XLY": "Consumer Discretionary",
    "XLU": "Utilities",
    "XLB": "Materials",
    "XLC": "Communication Services",
    "XLRE": "Real Estate",
}


class MarketRegimeIndicatorsTool(Tool):
    """Tool for fetching comprehensive market regime indicators.

    Provides:
    - VIX (Volatility Index) levels
    - Market Breadth (sector ETF performance vs. market)
    - Sector Rotation Signals (relative strength and momentum)

    All data is fetched using free sources via yfinance.
    """

    def __init__(self, market_data_provider: MarketDataProvider) -> None:
        """Initialize tool with market data provider.

        Args:
            market_data_provider: Provider for historical market data
        """
        self._provider = market_data_provider

    def get_name(self) -> str:
        """Get tool name."""
        return "get_market_regime_indicators"

    def get_description(self) -> str:
        """Get tool description."""
        return (
            "Get comprehensive market regime indicators including VIX (volatility index), "
            "market breadth (sector ETF analysis), and sector rotation signals. "
            "All data is fetched from free sources."
        )

    def get_schema(self) -> ToolSchema:
        """Get tool schema."""
        return ToolSchema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "type": "object",
                "properties": {
                    "market_index": {
                        "type": "string",
                        "description": "Market index symbol for comparison (default: 'SPY')",
                        "default": "SPY",
                    },
                    "lookback_days": {
                        "type": "integer",
                        "description": "Number of days to analyze (default: 252, ~1 trading year)",
                        "default": 252,
                    },
                    "include_vix": {
                        "type": "boolean",
                        "description": "Include VIX volatility index data (default: true)",
                        "default": True,
                    },
                    "include_market_breadth": {
                        "type": "boolean",
                        "description": "Include market breadth analysis from sector ETFs (default: true)",
                        "default": True,
                    },
                    "include_sector_rotation": {
                        "type": "boolean",
                        "description": "Include sector rotation signals (default: true)",
                        "default": True,
                    },
                },
                "required": [],
            },
            returns={
                "type": "object",
                "description": "Market regime indicators including VIX, market breadth, and sector rotation",
            },
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute market regime indicators analysis."""
        try:
            validated = self.validate_parameters(**kwargs)
            market_index = validated.get("market_index", "SPY").upper()
            lookback_days = validated.get("lookback_days", 252)
            include_vix = validated.get("include_vix", True)
            include_market_breadth = validated.get("include_market_breadth", True)
            include_sector_rotation = validated.get("include_sector_rotation", True)

            # Calculate date range
            # Add extra buffer to ensure we have enough data for 200-day MA calculation
            # 252 trading days + 60 buffer = ~312 calendar days to account for weekends/holidays
            end_date = datetime.now()
            start_date = end_date - timedelta(
                days=lookback_days + 60
            )  # Increased buffer for weekends/holidays and to ensure 200+ trading days

            results: dict[str, Any] = {
                "market_index": market_index,
                "lookback_days": lookback_days,
                "analysis_date": end_date.isoformat(),
            }

            # Fetch shared data once if needed by multiple indicators
            market_data = None
            sector_data_cache: dict[str, list] = {}
            needs_shared_data = include_market_breadth or include_sector_rotation

            if needs_shared_data:
                try:
                    # Fetch market index data once (used by both breadth and rotation)
                    market_data = await self._provider.get_historical_data(
                        market_index, start_date, end_date, interval="1d"
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to fetch market data for breadth/rotation analysis",
                        market_index=market_index,
                        error=str(e),
                    )
                    market_data = None

                # Fetch all sector ETF data once (used by both breadth and rotation)
                for sector_symbol in SECTOR_ETFS.keys():
                    try:
                        sector_data = await self._provider.get_historical_data(
                            sector_symbol, start_date, end_date, interval="1d"
                        )
                        if sector_data:
                            sector_data_cache[sector_symbol] = sector_data
                    except Exception as e:
                        logger.debug(
                            "Failed to fetch sector data",
                            sector=sector_symbol,
                            error=str(e),
                        )

            # Fetch VIX data
            if include_vix:
                try:
                    vix_data = await self._fetch_vix_data(start_date, end_date)
                    results["vix"] = vix_data
                except Exception as e:
                    logger.warning("Failed to fetch VIX data", error=str(e))
                    results["vix"] = {
                        "available": False,
                        "data_points": 0,
                        "error": f"Failed to fetch VIX data: {str(e)}",
                    }

            # Fetch market breadth (using cached data)
            if include_market_breadth:
                try:
                    breadth_data = await self._calculate_market_breadth(
                        market_index, start_date, end_date, market_data, sector_data_cache
                    )
                    results["market_breadth"] = breadth_data
                except Exception as e:
                    logger.warning("Failed to calculate market breadth", error=str(e))
                    results["market_breadth"] = {
                        "available": False,
                        "error": f"Failed to calculate market breadth: {str(e)}",
                    }

            # Fetch sector rotation signals (using cached data)
            if include_sector_rotation:
                try:
                    rotation_data = await self._calculate_sector_rotation(
                        market_index, start_date, end_date, market_data, sector_data_cache
                    )
                    results["sector_rotation"] = rotation_data
                except Exception as e:
                    logger.warning("Failed to calculate sector rotation", error=str(e))
                    results["sector_rotation"] = {
                        "available": False,
                        "market_return_20d": 0.0,
                        "market_return_60d": 0.0,
                        "error": f"Failed to calculate sector rotation: {str(e)}",
                    }

            return ToolResult(
                success=True,
                data=results,
                metadata={
                    "market_index": market_index,
                    "lookback_days": lookback_days,
                    "indicators_included": {
                        "vix": include_vix,
                        "market_breadth": include_market_breadth,
                        "sector_rotation": include_sector_rotation,
                    },
                },
            )

        except Exception as e:
            logger.error("Failed to get market regime indicators", error=str(e), exc_info=True)
            return ToolResult(
                success=False,
                data=None,
                error=f"Failed to get market regime indicators: {str(e)}",
                metadata={"error_type": type(e).__name__},
            )

    async def _fetch_vix_data(self, start_date: datetime, end_date: datetime) -> dict[str, Any]:
        """Fetch VIX volatility index data.

        Args:
            start_date: Start date for data
            end_date: End date for data

        Returns:
            Dictionary with VIX data including current level, recent average, and trend
        """
        try:
            vix_data_list = await self._provider.get_historical_data(
                "^VIX", start_date, end_date, interval="1d"
            )

            if not vix_data_list:
                return {
                    "available": False,
                    "data_points": 0,
                    "error": "No VIX data available",
                }

            # Extract closing prices
            vix_prices = [float(d.close_price) for d in vix_data_list if d.close_price is not None]

            if not vix_prices:
                return {
                    "available": False,
                    "data_points": 0,
                    "error": "No valid VIX price data",
                }

            current_vix = vix_prices[-1]
            recent_avg = sum(vix_prices[-20:]) / min(20, len(vix_prices))
            recent_max = max(vix_prices[-20:]) if len(vix_prices) >= 20 else max(vix_prices)
            recent_min = min(vix_prices[-20:]) if len(vix_prices) >= 20 else min(vix_prices)

            # Classify VIX level
            # VIX interpretation:
            # < 15: Low volatility (complacent market)
            # 15-25: Normal volatility
            # > 25: High volatility (fearful market)
            # > 30: Very high volatility (panic)
            if current_vix < 15:
                vix_regime = "low"
                vix_sentiment = "complacent"
            elif current_vix < 25:
                vix_regime = "normal"
                vix_sentiment = "normal"
            elif current_vix < 30:
                vix_regime = "high"
                vix_sentiment = "fearful"
            else:
                vix_regime = "very_high"
                vix_sentiment = "panic"

            return {
                "available": True,
                "current_vix": round(current_vix, 2),
                "recent_average_20d": round(recent_avg, 2),
                "recent_max_20d": round(recent_max, 2),
                "recent_min_20d": round(recent_min, 2),
                "regime": vix_regime,
                "sentiment": vix_sentiment,
                "data_points": len(vix_prices),
            }

        except Exception as e:
            logger.warning("Failed to fetch VIX data", error=str(e))
            return {
                "available": False,
                "data_points": 0,
                "error": str(e),
            }

    async def _calculate_market_breadth(
        self,
        market_index: str,
        start_date: datetime,
        end_date: datetime,
        market_data: list | None = None,
        sector_data_cache: dict[str, list] | None = None,
    ) -> dict[str, Any]:
        """Calculate market breadth using sector ETFs.

        Market breadth measures how many sectors are participating in market moves.
        Strong breadth = many sectors moving together (healthy market)
        Weak breadth = few sectors moving (narrow market, potential weakness)

        Args:
            market_index: Market index symbol (e.g., "SPY")
            start_date: Start date for analysis
            end_date: End date for analysis

        Returns:
            Dictionary with market breadth metrics
        """
        try:
            # Use provided market data or fetch if not provided
            if market_data is None:
                market_data = await self._provider.get_historical_data(
                    market_index, start_date, end_date, interval="1d"
                )

            if not market_data:
                return {
                    "available": False,
                    "sectors_above_50ma": 0,
                    "sectors_outperforming": 0,
                    "total_sectors_analyzed": 0,
                    "error": f"No data available for {market_index}",
                }

            market_prices = [float(d.close_price) for d in market_data if d.close_price is not None]

            if len(market_prices) < 20:
                return {
                    "available": False,
                    "sectors_above_50ma": 0,
                    "sectors_outperforming": 0,
                    "total_sectors_analyzed": 0,
                    "error": "Insufficient market data for breadth calculation",
                }

            # Get current market price
            current_market_price = market_prices[-1]

            # Use cached sector data or fetch if not provided
            if sector_data_cache is None:
                sector_data_cache = {}

            sector_performance: dict[str, dict[str, Any]] = {}
            sectors_above_ma = 0
            sectors_above_market = 0
            total_sectors = 0

            # Get current date for YTD calculation
            # Use UTC to ensure timezone consistency with StockData timestamps
            current_date = datetime.now(UTC)
            year_start_date = datetime(current_date.year, 1, 1, tzinfo=UTC)

            # First pass: collect all sector data and market caps
            sector_data_dict: dict[str, dict[str, Any]] = {}
            market_caps: dict[str, int | None] = {}

            for sector_symbol, sector_name in SECTOR_ETFS.items():
                try:
                    # Use cached data if available, otherwise fetch
                    if sector_symbol in sector_data_cache:
                        sector_data = sector_data_cache[sector_symbol]
                    else:
                        sector_data = await self._provider.get_historical_data(
                            sector_symbol, start_date, end_date, interval="1d"
                        )

                    if not sector_data:
                        continue

                    sector_prices = [
                        float(d.close_price) for d in sector_data if d.close_price is not None
                    ]

                    if (
                        len(sector_prices) < 50
                    ):  # Need at least 50 days for 50-day MA (minimum requirement)
                        continue

                    # Fetch market cap from quote with retry logic
                    # Some ETFs (like XLC, XLRE) may have intermittent API issues
                    market_cap = None
                    max_retries = 2
                    for attempt in range(max_retries):
                        try:
                            quote = await self._provider.get_quote(sector_symbol)
                            market_cap = quote.get("market_cap")
                            if market_cap:
                                market_caps[sector_symbol] = int(market_cap)
                                break
                            else:
                                # If quote succeeded but market_cap is None, try alternative calculation
                                # For ETFs, we can estimate from current price and shares outstanding
                                current_price = quote.get("current_price")
                                if current_price and hasattr(current_price, "__float__"):
                                    # Try to get shares outstanding from quote if available
                                    # Note: This is a fallback - yfinance may not provide this for all ETFs
                                    logger.debug(
                                        "Market cap not available in quote, attempting alternative",
                                        sector=sector_symbol,
                                    )
                                market_caps[sector_symbol] = None
                                break
                        except Exception as e:
                            if attempt < max_retries - 1:
                                # Wait a bit before retry (exponential backoff)
                                await asyncio.sleep(0.5 * (attempt + 1))
                                logger.debug(
                                    "Retrying market cap fetch",
                                    sector=sector_symbol,
                                    attempt=attempt + 1,
                                    error=str(e),
                                )
                            else:
                                logger.debug(
                                    "Failed to fetch market cap for sector after retries",
                                    sector=sector_symbol,
                                    error=str(e),
                                )
                                market_caps[sector_symbol] = None

                    # Store sector data for processing
                    sector_data_dict[sector_symbol] = {
                        "name": sector_name,
                        "prices": sector_prices,
                        "data": sector_data,
                    }

                except Exception as e:
                    logger.debug(
                        "Failed to fetch sector data",
                        sector=sector_symbol,
                        error=str(e),
                    )
                    continue

            # Calculate market cap ranks
            # Sort sectors by market cap (largest first), assign ranks
            sorted_sectors_by_cap = sorted(
                [
                    (symbol, cap)
                    for symbol, cap in market_caps.items()
                    if cap is not None and symbol in sector_data_dict
                ],
                key=lambda x: x[1],
                reverse=True,
            )
            market_cap_ranks: dict[str, int] = {}
            for rank, (symbol, _) in enumerate(sorted_sectors_by_cap, start=1):
                market_cap_ranks[symbol] = rank

            # Second pass: calculate all metrics for each sector
            for sector_symbol, sector_info in sector_data_dict.items():
                try:
                    sector_name = sector_info["name"]
                    sector_prices = sector_info["prices"]
                    sector_data = sector_info["data"]

                    current_sector_price = sector_prices[-1]

                    # Calculate moving averages
                    sector_ma_50 = _calculate_moving_average(sector_prices, 50)
                    # Only calculate 200-day MA if we have enough data
                    sector_ma_200 = (
                        _calculate_moving_average(sector_prices, 200)
                        if len(sector_prices) >= 200
                        else [None] * len(sector_prices)
                    )
                    current_sector_ma_50 = (
                        sector_ma_50[-1] if sector_ma_50[-1] is not None else current_sector_price
                    )
                    current_sector_ma_200 = (
                        sector_ma_200[-1] if sector_ma_200[-1] is not None else None
                    )

                    # Calculate returns for different periods
                    return_1d = None
                    return_5d = None
                    return_120d = None
                    return_ytd = None

                    if len(sector_prices) >= 2:
                        return_1d = (
                            (sector_prices[-1] - sector_prices[-2]) / sector_prices[-2] * 100
                            if sector_prices[-2] > 0
                            else None
                        )
                    if len(sector_prices) >= 6:
                        return_5d = (
                            (sector_prices[-1] - sector_prices[-6]) / sector_prices[-6] * 100
                            if sector_prices[-6] > 0
                            else None
                        )
                    if len(sector_prices) >= 121:
                        return_120d = (
                            (sector_prices[-1] - sector_prices[-121]) / sector_prices[-121] * 100
                            if sector_prices[-121] > 0
                            else None
                        )

                    # Calculate YTD return
                    # Find the price closest to year start
                    if sector_data:
                        # Find the first data point on or after year start
                        # Normalize timestamps for comparison (handle both timezone-aware and naive)
                        def normalize_datetime(dt: datetime) -> datetime:
                            """Normalize datetime to UTC-aware for comparison."""
                            if dt.tzinfo is None:
                                # If naive, assume UTC
                                return dt.replace(tzinfo=UTC)
                            # If aware, convert to UTC
                            return dt.astimezone(UTC)

                        normalized_year_start = normalize_datetime(year_start_date)
                        year_start_prices = [
                            (d.timestamp, float(d.close_price))
                            for d in sector_data
                            if d.close_price is not None
                            and normalize_datetime(d.timestamp) >= normalized_year_start
                        ]
                        if year_start_prices:
                            # Get the earliest price in the year
                            year_start_prices.sort(key=lambda x: x[0])
                            ytd_start_price = year_start_prices[0][1]
                            return_ytd = (
                                (current_sector_price - ytd_start_price) / ytd_start_price * 100
                                if ytd_start_price > 0
                                else None
                            )

                    # Calculate RSI
                    rsi_14d = _calculate_rsi(sector_prices, period=14)

                    # Calculate volatility (20-day)
                    volatility_list = _calculate_volatility(sector_prices, window=20)
                    volatility_20d = (
                        volatility_list[-1] * 100
                        if volatility_list and volatility_list[-1] is not None
                        else None
                    )  # Convert to percentage

                    # Calculate performance vs. market
                    market_return = (
                        (current_market_price - market_prices[0]) / market_prices[0] * 100
                        if market_prices[0] > 0
                        else 0
                    )
                    sector_return = (
                        (current_sector_price - sector_prices[0]) / sector_prices[0] * 100
                        if sector_prices[0] > 0
                        else 0
                    )
                    relative_performance = sector_return - market_return

                    # Check if above MA
                    above_ma = (
                        current_sector_price > current_sector_ma_50
                        if current_sector_ma_50
                        else False
                    )
                    above_200ma = (
                        current_sector_price > current_sector_ma_200
                        if current_sector_ma_200 is not None
                        else None
                    )
                    above_market = relative_performance > 0

                    if above_ma:
                        sectors_above_ma += 1
                    if above_market:
                        sectors_above_market += 1

                    total_sectors += 1

                    sector_performance[sector_symbol] = {
                        "name": sector_name,
                        "current_price": round(current_sector_price, 2),
                        "above_50ma": above_ma,
                        "relative_performance_pct": round(relative_performance, 2),
                        "sector_return_pct": round(sector_return, 2),
                        "market_return_pct": round(market_return, 2),
                        "return_1d": round(return_1d, 2) if return_1d is not None else None,
                        "return_5d": round(return_5d, 2) if return_5d is not None else None,
                        "return_120d": round(return_120d, 2) if return_120d is not None else None,
                        "return_ytd": round(return_ytd, 2) if return_ytd is not None else None,
                        "price_above_200ma": above_200ma,
                        "rsi_14d": round(rsi_14d, 2) if rsi_14d is not None else None,
                        "volatility_20d": (
                            round(volatility_20d, 2) if volatility_20d is not None else None
                        ),
                        "market_cap": market_caps.get(sector_symbol),
                        "market_cap_rank": market_cap_ranks.get(sector_symbol),
                    }

                except Exception as e:
                    logger.debug(
                        "Failed to calculate sector metrics",
                        sector=sector_symbol,
                        error=str(e),
                    )
                    continue

            if total_sectors == 0:
                return {
                    "available": False,
                    "sectors_above_50ma": 0,
                    "sectors_outperforming": 0,
                    "total_sectors_analyzed": 0,
                    "error": "No sector data available for breadth calculation",
                }

            # Calculate breadth metrics
            breadth_ratio = sectors_above_ma / total_sectors if total_sectors > 0 else 0
            participation_ratio = sectors_above_market / total_sectors if total_sectors > 0 else 0

            # Classify breadth
            # Strong: > 70% of sectors above MA and outperforming
            # Moderate: 40-70% participating
            # Weak: < 40% participating
            if breadth_ratio >= 0.7 and participation_ratio >= 0.7:
                breadth_regime = "strong"
            elif breadth_ratio >= 0.4 and participation_ratio >= 0.4:
                breadth_regime = "moderate"
            else:
                breadth_regime = "weak"

            return {
                "available": True,
                "breadth_ratio": round(breadth_ratio * 100, 1),  # Percentage
                "participation_ratio": round(participation_ratio * 100, 1),  # Percentage
                "sectors_above_50ma": sectors_above_ma,
                "sectors_outperforming": sectors_above_market,
                "total_sectors_analyzed": total_sectors,
                "regime": breadth_regime,
                "sector_details": sector_performance,
            }

        except Exception as e:
            logger.warning("Failed to calculate market breadth", error=str(e))
            return {
                "available": False,
                "sectors_above_50ma": 0,
                "sectors_outperforming": 0,
                "total_sectors_analyzed": 0,
                "error": str(e),
            }

    async def _calculate_sector_rotation(
        self,
        market_index: str,
        start_date: datetime,
        end_date: datetime,
        market_data: list | None = None,
        sector_data_cache: dict[str, list] | None = None,
    ) -> dict[str, Any]:
        """Calculate sector rotation signals.

        Sector rotation identifies which sectors are gaining/losing momentum relative to the market.
        This helps identify:
        - Defensive rotation (utilities, staples outperform)
        - Growth rotation (technology, discretionary outperform)
        - Value rotation (financials, industrials outperform)

        Args:
            market_index: Market index symbol (e.g., "SPY")
            start_date: Start date for analysis
            end_date: End date for analysis

        Returns:
            Dictionary with sector rotation signals
        """
        try:
            # Use provided market data or fetch if not provided
            if market_data is None:
                market_data = await self._provider.get_historical_data(
                    market_index, start_date, end_date, interval="1d"
                )

            if not market_data:
                return {
                    "available": False,
                    "market_return_20d": 0.0,
                    "market_return_60d": 0.0,
                    "error": f"No data available for {market_index}",
                }

            market_prices = [float(d.close_price) for d in market_data if d.close_price is not None]

            if len(market_prices) < 20:
                return {
                    "available": False,
                    "market_return_20d": 0.0,
                    "market_return_60d": 0.0,
                    "error": "Insufficient market data for rotation calculation",
                }

            # Calculate market returns
            market_return_20d = (
                (market_prices[-1] - market_prices[-20]) / market_prices[-20] * 100
                if len(market_prices) >= 20 and market_prices[-20] > 0
                else 0
            )
            market_return_60d = (
                (market_prices[-1] - market_prices[-60]) / market_prices[-60] * 100
                if len(market_prices) >= 60 and market_prices[-60] > 0
                else 0
            )

            # Use cached sector data or fetch if not provided
            if sector_data_cache is None:
                sector_data_cache = {}

            # Analyze sector ETFs using cached data
            sector_momentum: list[dict[str, Any]] = []

            for sector_symbol, sector_name in SECTOR_ETFS.items():
                try:
                    # Use cached data if available, otherwise fetch
                    if sector_symbol in sector_data_cache:
                        sector_data = sector_data_cache[sector_symbol]
                    else:
                        sector_data = await self._provider.get_historical_data(
                            sector_symbol, start_date, end_date, interval="1d"
                        )

                    if not sector_data or len(sector_data) < 60:
                        continue

                    sector_prices = [
                        float(d.close_price) for d in sector_data if d.close_price is not None
                    ]

                    if len(sector_prices) < 60:
                        continue

                    # Calculate sector returns
                    sector_return_20d = (
                        (sector_prices[-1] - sector_prices[-20]) / sector_prices[-20] * 100
                        if len(sector_prices) >= 20 and sector_prices[-20] > 0
                        else 0
                    )
                    sector_return_60d = (
                        (sector_prices[-1] - sector_prices[-60]) / sector_prices[-60] * 100
                        if len(sector_prices) >= 60 and sector_prices[-60] > 0
                        else 0
                    )

                    # Calculate relative momentum
                    relative_momentum_20d = sector_return_20d - market_return_20d
                    relative_momentum_60d = sector_return_60d - market_return_60d

                    # Momentum score (weighted: recent momentum more important)
                    momentum_score = (relative_momentum_20d * 0.6) + (relative_momentum_60d * 0.4)

                    sector_momentum.append(
                        {
                            "symbol": sector_symbol,
                            "name": sector_name,
                            "momentum_score": round(momentum_score, 2),
                            "relative_momentum_20d": round(relative_momentum_20d, 2),
                            "relative_momentum_60d": round(relative_momentum_60d, 2),
                            "sector_return_20d": round(sector_return_20d, 2),
                            "sector_return_60d": round(sector_return_60d, 2),
                        }
                    )

                except Exception as e:
                    logger.debug(
                        "Failed to fetch sector data for rotation",
                        sector=sector_symbol,
                        error=str(e),
                    )
                    continue

            if not sector_momentum:
                return {
                    "available": False,
                    "market_return_20d": 0.0,
                    "market_return_60d": 0.0,
                    "error": "No sector data available for rotation calculation",
                }

            # Sort by momentum score (highest first)
            sector_momentum.sort(key=lambda x: x["momentum_score"], reverse=True)

            # Identify rotation themes
            # Top 3 sectors = leading rotation
            # Bottom 3 sectors = lagging rotation
            leading_sectors = sector_momentum[:3]
            lagging_sectors = sector_momentum[-3:]

            # Classify rotation theme
            # Check if defensive sectors (utilities, staples) are leading
            defensive_symbols = {"XLU", "XLP"}
            defensive_leading = any(s["symbol"] in defensive_symbols for s in leading_sectors)

            # Check if growth sectors (technology, discretionary) are leading
            growth_symbols = {"XLK", "XLY"}
            growth_leading = any(s["symbol"] in growth_symbols for s in leading_sectors)

            # Check if value sectors (financials, industrials) are leading
            value_symbols = {"XLF", "XLI"}
            value_leading = any(s["symbol"] in value_symbols for s in leading_sectors)

            if defensive_leading and not growth_leading:
                rotation_theme = "defensive"
            elif growth_leading and not defensive_leading:
                rotation_theme = "growth"
            elif value_leading:
                rotation_theme = "value"
            else:
                rotation_theme = "mixed"

            return {
                "available": True,
                "rotation_theme": rotation_theme,
                "leading_sectors": leading_sectors,
                "lagging_sectors": lagging_sectors,
                "all_sectors_ranked": sector_momentum,
                "market_return_20d": round(market_return_20d, 2),
                "market_return_60d": round(market_return_60d, 2),
            }

        except Exception as e:
            logger.warning("Failed to calculate sector rotation", error=str(e))
            return {
                "available": False,
                "market_return_20d": 0.0,
                "market_return_60d": 0.0,
                "error": str(e),
            }


def create_market_regime_indicators_tool(
    market_data_provider: MarketDataProvider,
) -> MarketRegimeIndicatorsTool:
    """Create market regime indicators tool.

    Args:
        market_data_provider: Market data provider instance

    Returns:
        MarketRegimeIndicatorsTool instance
    """
    return MarketRegimeIndicatorsTool(market_data_provider)
