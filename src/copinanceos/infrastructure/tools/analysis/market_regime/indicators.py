"""Market regime indicators tool.

This module provides tools for fetching comprehensive market regime indicators including:
- VIX (Volatility Index)
- Market Breadth (sector ETF analysis)
- Sector Rotation Signals

All data sources are free and use existing yfinance provider.
"""

from datetime import datetime, timedelta
from typing import Any

import structlog

from copinanceos.domain.ports.data_providers import MarketDataProvider
from copinanceos.domain.ports.tools import Tool, ToolResult, ToolSchema
from copinanceos.infrastructure.tools.analysis.market_regime.base import (
    _calculate_moving_average,
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
            end_date = datetime.now()
            start_date = end_date - timedelta(
                days=lookback_days + 30
            )  # Add buffer for weekends/holidays

            results: dict[str, Any] = {
                "market_index": market_index,
                "lookback_days": lookback_days,
                "analysis_date": end_date.isoformat(),
            }

            # Fetch VIX data
            if include_vix:
                vix_data = await self._fetch_vix_data(start_date, end_date)
                results["vix"] = vix_data

            # Fetch market breadth
            if include_market_breadth:
                breadth_data = await self._calculate_market_breadth(
                    market_index, start_date, end_date
                )
                results["market_breadth"] = breadth_data

            # Fetch sector rotation signals
            if include_sector_rotation:
                rotation_data = await self._calculate_sector_rotation(
                    market_index, start_date, end_date
                )
                results["sector_rotation"] = rotation_data

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
                    "error": "No VIX data available",
                }

            # Extract closing prices
            vix_prices = [float(d.close_price) for d in vix_data_list if d.close_price is not None]

            if not vix_prices:
                return {
                    "available": False,
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
                "error": str(e),
            }

    async def _calculate_market_breadth(
        self, market_index: str, start_date: datetime, end_date: datetime
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
            # Fetch market index data
            market_data = await self._provider.get_historical_data(
                market_index, start_date, end_date, interval="1d"
            )

            if not market_data:
                return {
                    "available": False,
                    "error": f"No data available for {market_index}",
                }

            market_prices = [float(d.close_price) for d in market_data if d.close_price is not None]

            if len(market_prices) < 20:
                return {
                    "available": False,
                    "error": "Insufficient market data for breadth calculation",
                }

            # Get current market price
            current_market_price = market_prices[-1]

            # Fetch sector ETF data
            sector_performance: dict[str, dict[str, Any]] = {}
            sectors_above_ma = 0
            sectors_above_market = 0
            total_sectors = 0

            for sector_symbol, sector_name in SECTOR_ETFS.items():
                try:
                    sector_data = await self._provider.get_historical_data(
                        sector_symbol, start_date, end_date, interval="1d"
                    )

                    if not sector_data:
                        continue

                    sector_prices = [
                        float(d.close_price) for d in sector_data if d.close_price is not None
                    ]

                    if len(sector_prices) < 50:
                        continue

                    # Calculate sector metrics
                    sector_ma_50 = _calculate_moving_average(sector_prices, 50)
                    current_sector_price = sector_prices[-1]
                    current_sector_ma = (
                        sector_ma_50[-1] if sector_ma_50[-1] is not None else current_sector_price
                    )

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
                        current_sector_price > current_sector_ma if current_sector_ma else False
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
                    }

                except Exception as e:
                    logger.debug(
                        "Failed to fetch sector data",
                        sector=sector_symbol,
                        error=str(e),
                    )
                    continue

            if total_sectors == 0:
                return {
                    "available": False,
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
                "error": str(e),
            }

    async def _calculate_sector_rotation(
        self, market_index: str, start_date: datetime, end_date: datetime
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
            # Fetch market index data
            market_data = await self._provider.get_historical_data(
                market_index, start_date, end_date, interval="1d"
            )

            if not market_data:
                return {
                    "available": False,
                    "error": f"No data available for {market_index}",
                }

            market_prices = [float(d.close_price) for d in market_data if d.close_price is not None]

            if len(market_prices) < 20:
                return {
                    "available": False,
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

            # Fetch and analyze sector ETFs
            sector_momentum: list[dict[str, Any]] = []

            for sector_symbol, sector_name in SECTOR_ETFS.items():
                try:
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
