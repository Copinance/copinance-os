"""Rule-based market regime detection tools.

This module provides rule-based tools for detecting different market regimes using
technical indicators, moving averages, and threshold-based logic:
- Trend detection (bull, bear, neutral) using MA crossovers
- Volatility regimes (high, low, normal) using rolling volatility
- Market cycles and regime transitions using Wyckoff methodology

Methodology Improvements:
- Uses log-returns (r_t = ln(P_t / P_{t-1})) for better statistical properties:
  * Additivity: multi-period returns are sums of log-returns
  * Better handling of high-volatility stocks (e.g., MSTR)
  * More symmetric distribution
- Uses volatility-scaled thresholds instead of hard thresholds:
  * AdjMomentum = log_return / σ
  * Avoids penalizing low-volatility stocks
  * Thresholds: ±0.25σ (medium confidence), ±1.0σ (high confidence)

Academic Foundations & References:

Trend & Moving Averages:
    - Brock, W., Lakonishok, J., & LeBaron, B. (1992). Simple Technical Trading Rules
      and the Stochastic Properties of Stock Returns. Journal of Finance, 47(5), 1731-1764.
      → Validates MA crossovers and momentum effectiveness

    - Faber, M. T. (2007). A Quantitative Approach to Tactical Asset Allocation.
      Journal of Wealth Management, 9(4), 69-79.
      → 10-month MA regime filter (bull/bear logic foundation)

Momentum:
    - Jegadeesh, N., & Titman, S. (1993). Returns to Buying Winners and Selling Losers:
      Implications for Stock Market Efficiency. Journal of Finance, 48(1), 65-91.
      → Cross-sectional and time-series momentum

    - Moskowitz, T. J., Ooi, Y. H., & Pedersen, L. H. (2012). Time Series Momentum.
      Journal of Financial Economics, 104(2), 228-250.
      → Momentum and trend alignment logic

Volatility:
    - Andersen, T. G., & Bollerslev, T. (1998). Answering the Skeptics: Yes, Standard
      Volatility Models Do Provide Accurate Forecasts. International Economic Review,
      39(4), 885-905.
      → Validates realized volatility calculations

    - RiskMetrics Technical Document (J.P. Morgan, 1996).
      → Rolling volatility with annualization methodology

Market Regimes & Cycles:
    - Hamilton, J. D. (1989). A New Approach to the Economic Analysis of Nonstationary
      Time Series and the Business Cycle. Econometrica, 57(2), 357-384.
      → Regime switching models (conceptual foundation)

    - Wyckoff Method (1930s, modernized by various practitioners).
      → Accumulation / Markup / Distribution / Markdown cycle phases

    - Lo, A. W. (2004). The Adaptive Markets Hypothesis: Market Efficiency from an
      Evolutionary Perspective. Journal of Portfolio Management, 30(5), 15-29.
      → Why regimes exist and change over time
"""

from datetime import datetime, timedelta
from math import log
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import structlog

from copinanceos.domain.ports.data_providers import MarketDataProvider
from copinanceos.domain.ports.tools import Tool, ToolResult, ToolSchema

logger = structlog.get_logger(__name__)


def _calculate_moving_average(prices: list[float], window: int) -> list[float | None]:
    """Calculate simple moving average using pandas.

    Based on Brock, Lakonishok, & LeBaron (1992) methodology for technical trading rules.
    Simple moving averages are fundamental to trend-following strategies and regime detection.

    Uses pandas rolling window operations for efficient vectorized calculations.

    Args:
        prices: List of prices
        window: Moving average window size

    Returns:
        List of moving average values (None for insufficient data)
    """
    if len(prices) < window:
        return [None] * len(prices)

    # Use pandas for efficient rolling mean calculation
    series = pd.Series(prices)
    ma_series = series.rolling(window=window, min_periods=window).mean()

    # Convert to list with None for NaN values (maintains backward compatibility)
    return [None if pd.isna(val) else float(val) for val in ma_series]


def _calculate_log_returns(prices: list[float]) -> list[float]:
    """Calculate log-returns: r_t = ln(P_t / P_{t-1}) using pandas.

    Log-returns have better statistical properties:
    - Additivity: multi-period returns are sums of log-returns
    - Better handling of high-volatility stocks
    - More symmetric distribution

    Uses pandas for efficient vectorized calculations.

    Args:
        prices: List of prices

    Returns:
        List of log-returns (one less than input prices)
    """
    if len(prices) < 2:
        return []

    # Use pandas for efficient log-return calculation
    # Calculate log(P_t / P_{t-1}) = log(P_t) - log(P_{t-1})
    log_prices = pd.Series([log(p) if p > 0 else 0.0 for p in prices])
    log_returns = log_prices.diff()

    # Return as list, skipping first NaN value (first price has no previous price)
    return [float(val) if pd.notna(val) else 0.0 for val in log_returns[1:]]


def _calculate_volatility(prices: list[float], window: int = 20) -> list[float | None]:
    """Calculate rolling volatility (standard deviation of log-returns) using pandas.

    Implements realized volatility methodology as validated by Andersen & Bollerslev (1998).
    Uses RiskMetrics (J.P. Morgan, 1996) approach with annualization for daily data.
    Uses log-returns for better statistical properties.

    Uses pandas for efficient vectorized rolling standard deviation calculations.

    Args:
        prices: List of prices
        window: Window size for volatility calculation

    Returns:
        List of volatility values (None for insufficient data), annualized
    """
    if len(prices) < window + 1:
        return [None] * len(prices)

    # Use pandas for efficient calculation
    # Calculate log-returns using pandas
    # Calculate log(P_t / P_{t-1}) = log(P_t) - log(P_{t-1})
    log_prices = pd.Series([log(p) if p > 0 else 0.0 for p in prices])
    log_returns = log_prices.diff()

    # Calculate rolling standard deviation of log-returns
    # min_periods=window ensures we only get values when we have enough data
    # Note: log_returns[0] is NaN (no previous price), so we need window valid returns
    # starting from log_returns[1], which means first valid volatility is at index window+1
    rolling_std = log_returns.rolling(window=window, min_periods=window).std()

    # Annualize (assuming 252 trading days per year)
    annualized_vol = rolling_std * (252**0.5)

    # Convert to list with None for NaN values
    # Structure: [None] (first price) + [None] * window (need window returns) + valid values
    result: list[float | None] = [None]  # First price (index 0) has no return
    # Add None for indices 1 to window (need window log-returns for first valid volatility)
    result.extend([None] * window)
    # Add valid volatility values (starting from index window+1)
    result.extend([None if pd.isna(val) else float(val) for val in annualized_vol[window + 1 :]])

    return result


def _classify_volatility_regime(volatility: float, historical_vols: list[float]) -> str:
    """Classify volatility regime based on current vs historical volatility.

    Uses μ ± σ thresholds for classification. This approach is:
    - Robust and stable on individual stocks
    - Interpretable and explainable
    - Less prone to overfitting than GARCH models on retail horizons

    Future improvements:
    - Percentile-based regimes (e.g., top 80% → high, bottom 20% → low)
    - EWMA volatility (RiskMetrics style) for more responsive estimates

    Args:
        volatility: Current volatility
        historical_vols: Historical volatility values

    Returns:
        Regime classification: 'high', 'normal', or 'low'
    """
    if not historical_vols:
        return "normal"

    mean_vol = sum(historical_vols) / len(historical_vols)
    std_vol = (
        (sum((v - mean_vol) ** 2 for v in historical_vols) / len(historical_vols)) ** 0.5
        if len(historical_vols) > 1
        else 0
    )

    if volatility > mean_vol + std_vol:
        return "high"
    elif volatility < mean_vol - std_vol:
        return "low"
    else:
        return "normal"


def _classify_volatility_regime_percentile(volatility: float, historical_vols: list[float]) -> str:
    """Classify volatility regime using percentile-based thresholds.

    Alternative classification method using percentiles instead of μ ± σ.
    Example: Top 80% → High, Bottom 20% → Low, Middle → Normal

    This approach is more robust to outliers and provides clearer regime boundaries.

    Args:
        volatility: Current volatility
        historical_vols: Historical volatility values

    Returns:
        Regime classification: 'high', 'normal', or 'low'
    """
    if not historical_vols:
        return "normal"

    sorted_vols = sorted(historical_vols)
    percentile_80 = (
        sorted_vols[int(len(sorted_vols) * 0.8)] if len(sorted_vols) > 0 else sorted_vols[-1]
    )
    percentile_20 = (
        sorted_vols[int(len(sorted_vols) * 0.2)] if len(sorted_vols) > 0 else sorted_vols[0]
    )

    if volatility >= percentile_80:
        return "high"
    elif volatility <= percentile_20:
        return "low"
    else:
        return "normal"


def _calculate_ewma_volatility(
    prices: list[float], lambda_param: float = 0.94
) -> list[float | None]:
    """Calculate EWMA (Exponentially Weighted Moving Average) volatility.

    RiskMetrics-style volatility using EWMA with decay factor λ (typically 0.94 for daily data).
    More responsive to recent changes than simple moving average.

    Formula: σ²_t = λ * σ²_{t-1} + (1 - λ) * r²_t

    This is a future improvement over simple rolling volatility:
    - More responsive to recent volatility changes
    - Better for risk management applications
    - Standard in RiskMetrics methodology

    Args:
        prices: List of prices
        lambda_param: Decay factor (default 0.94 for daily data, per RiskMetrics)

    Returns:
        List of EWMA volatility values (None for insufficient data), annualized

    Note:
        This function is implemented but not yet used by default.
        To use EWMA volatility, update MarketRegimeDetectVolatilityTool.
    """
    if len(prices) < 2:
        return [None] * len(prices)

    log_returns = _calculate_log_returns(prices)
    if not log_returns:
        return [None] * len(prices)

    # Initialize with first return squared
    ewma_variance = log_returns[0] ** 2
    ewma_vols: list[float | None] = [None]  # First price has no volatility

    for i in range(1, len(log_returns)):
        # EWMA variance: σ²_t = λ * σ²_{t-1} + (1 - λ) * r²_t
        ewma_variance = lambda_param * ewma_variance + (1 - lambda_param) * (log_returns[i] ** 2)
        # Annualize (assuming 252 trading days)
        ewma_vol = (ewma_variance**0.5) * (252**0.5)
        ewma_vols.append(ewma_vol)

    return ewma_vols


class MarketRegimeDetectTrendTool(Tool):
    """Tool for detecting market trend regimes (bull, bear, neutral).

    Uses moving averages and price momentum to classify market trends.

    Theoretical Foundation:
        - Faber (2007): 10-month MA regime filter methodology adapted for shorter timeframes
        - Brock, Lakonishok, & LeBaron (1992): MA crossover effectiveness
        - Moskowitz, Ooi, & Pedersen (2012): Time series momentum for trend alignment
    """

    def __init__(self, market_data_provider: MarketDataProvider) -> None:
        """Initialize tool with market data provider.

        Args:
            market_data_provider: Provider for historical market data
        """
        self._provider = market_data_provider

    def get_name(self) -> str:
        """Get tool name."""
        return "detect_market_trend"

    def get_description(self) -> str:
        """Get tool description."""
        return (
            "Detect market trend regime (bull, bear, or neutral) for a stock "
            "using moving averages and price momentum analysis."
        )

    def get_schema(self) -> ToolSchema:
        """Get tool schema."""
        return ToolSchema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol (e.g., 'AAPL', 'MSFT')",
                    },
                    "lookback_days": {
                        "type": "integer",
                        "description": "Number of days to analyze for trend detection",
                        "default": 200,
                    },
                    "short_ma_period": {
                        "type": "integer",
                        "description": "Short-term moving average period (days)",
                        "default": 50,
                    },
                    "long_ma_period": {
                        "type": "integer",
                        "description": "Long-term moving average period (days)",
                        "default": 200,
                    },
                },
                "required": ["symbol"],
            },
            returns={
                "type": "object",
                "description": "Trend detection results with regime classification and metrics",
            },
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute trend detection tool."""
        try:
            validated = self.validate_parameters(**kwargs)
            symbol = validated["symbol"].upper()
            lookback_days = validated.get("lookback_days", 200)
            short_ma = validated.get("short_ma_period", 50)
            long_ma = validated.get("long_ma_period", 200)

            # Get historical data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)

            historical_data = await self._provider.get_historical_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval="1d",
            )

            if not historical_data:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"No historical data available for {symbol}",
                    metadata={"symbol": symbol},
                )

            # Extract closing prices
            prices = [float(data.close_price) for data in historical_data]

            # Adapt parameters based on available data
            # If we don't have enough data for long MA, adjust to use available data
            if len(prices) < long_ma:
                if len(prices) < short_ma:
                    # Not enough data even for short MA - use minimal analysis
                    if len(prices) < 10:
                        return ToolResult(
                            success=False,
                            data=None,
                            error=(
                                f"Insufficient data for trend analysis: need at least 10 data points, "
                                f"got {len(prices)}. This stock may be newly listed or have limited trading history."
                            ),
                            metadata={
                                "symbol": symbol,
                                "data_points": len(prices),
                                "suggestion": "Try a stock with more trading history, or use a shorter lookback period.",
                            },
                        )
                    # Use minimal MAs
                    adjusted_short_ma = max(5, len(prices) // 3)
                    adjusted_long_ma = max(adjusted_short_ma + 5, len(prices) - 5)
                    short_ma = adjusted_short_ma
                    long_ma = adjusted_long_ma
                    logger.warning(
                        "Adjusted MA parameters due to limited data",
                        symbol=symbol,
                        data_points=len(prices),
                        adjusted_short_ma=short_ma,
                        adjusted_long_ma=long_ma,
                    )
                else:
                    # Have enough for short MA, but not long - use shorter long MA
                    adjusted_long_ma = max(short_ma + 10, len(prices) - 5)
                    long_ma = adjusted_long_ma
                    logger.warning(
                        "Adjusted long MA parameter due to limited data",
                        symbol=symbol,
                        data_points=len(prices),
                        adjusted_long_ma=long_ma,
                    )

            # Calculate moving averages
            short_ma_values = _calculate_moving_average(prices, short_ma)
            long_ma_values = _calculate_moving_average(prices, long_ma)

            # Get current values
            current_price = prices[-1]
            current_short_ma = short_ma_values[-1]
            current_long_ma = long_ma_values[-1]

            # Calculate log-return over period (better statistical properties)
            # r_t = ln(P_t / P_0) = ln(P_t) - ln(P_0)
            log_return = log(current_price / prices[0]) if prices[0] > 0 else 0.0
            price_change_pct = log_return * 100  # Convert to percentage for display

            # Calculate volatility for volatility-scaled thresholds
            # Use recent volatility (last 20 days) to scale thresholds
            recent_vol = None
            if len(prices) >= 21:
                recent_prices = prices[-21:]
                recent_log_returns = _calculate_log_returns(recent_prices)
                if recent_log_returns:
                    mean_ret = sum(recent_log_returns) / len(recent_log_returns)
                    variance = sum((r - mean_ret) ** 2 for r in recent_log_returns) / len(
                        recent_log_returns
                    )
                    recent_vol = (variance**0.5) * (252**0.5)  # Annualized volatility

            # Volatility-scaled momentum: AdjMomentum = (P_T - P_0) / (P_0 * σ)
            # This avoids penalizing low-volatility stocks
            if recent_vol and recent_vol > 0:
                # Use log-return scaled by volatility
                volatility_scaled_momentum = log_return / recent_vol
            else:
                # Fallback to unscaled if volatility unavailable
                volatility_scaled_momentum = log_return / 0.2  # Assume 20% annual vol as default

            # Determine trend using Faber (2007) methodology with volatility-scaled thresholds
            # Bull: price > short MA > long MA with positive momentum
            # Bear: price < short MA < long MA with negative momentum
            # Neutral: mixed signals or insufficient data
            # Thresholds are volatility-scaled: ±0.25σ for medium, ±1.0σ for high confidence
            if current_short_ma is None or current_long_ma is None:
                regime = "neutral"
                confidence = "low"
            elif current_price > current_short_ma > current_long_ma:
                if volatility_scaled_momentum > 1.0:
                    regime = "bull"
                    confidence = "high"
                elif volatility_scaled_momentum > 0.25:
                    regime = "bull"
                    confidence = "medium"
                else:
                    regime = "neutral"
                    confidence = "low"
            elif current_price < current_short_ma < current_long_ma:
                if volatility_scaled_momentum < -1.0:
                    regime = "bear"
                    confidence = "high"
                elif volatility_scaled_momentum < -0.25:
                    regime = "bear"
                    confidence = "medium"
                else:
                    regime = "neutral"
                    confidence = "low"
            else:
                regime = "neutral"
                confidence = "medium"

            # Calculate momentum using log-returns (20-day)
            # Based on Jegadeesh & Titman (1993) and Moskowitz, Ooi, & Pedersen (2012)
            # Time series momentum using log-returns for better statistical properties
            if len(prices) >= 20:
                momentum_20_log = log(current_price / prices[-20]) if prices[-20] > 0 else 0.0
                momentum_20 = momentum_20_log * 100  # Convert to percentage for display
            else:
                momentum_20 = 0.0

            # Check if parameters were adjusted
            original_short_ma = validated.get("short_ma_period", 50)
            original_long_ma = validated.get("long_ma_period", 200)
            parameters_adjusted = short_ma != original_short_ma or long_ma != original_long_ma

            result = {
                "symbol": symbol,
                "regime": regime,
                "confidence": confidence,
                "current_price": current_price,
                "price_change_pct": round(price_change_pct, 2),  # Log-return as percentage
                "log_return": round(log_return, 4),  # Raw log-return
                "volatility_scaled_momentum": round(volatility_scaled_momentum, 4),
                "recent_volatility": (
                    round(recent_vol * 100, 2) if recent_vol else None
                ),  # As percentage
                "momentum_20d_pct": round(momentum_20, 2),
                "short_ma": round(current_short_ma, 2) if current_short_ma else None,
                "long_ma": round(current_long_ma, 2) if current_long_ma else None,
                "ma_relationship": (
                    "bullish"
                    if current_short_ma and current_long_ma and current_short_ma > current_long_ma
                    else (
                        "bearish"
                        if current_short_ma
                        and current_long_ma
                        and current_short_ma < current_long_ma
                        else "neutral"
                    )
                ),
                "analysis_period_days": lookback_days,
                "data_points": len(prices),
                "parameters_adjusted": parameters_adjusted,
                "short_ma_period_used": short_ma,
                "long_ma_period_used": long_ma,
                "methodology": "log_returns_with_volatility_scaling",
            }

            if parameters_adjusted:
                result["note"] = (
                    f"Analysis adapted for limited data history. "
                    f"Used MA periods: {short_ma}/{long_ma} (requested: {original_short_ma}/{original_long_ma}). "
                    f"Results may have lower confidence."
                )

            return ToolResult(
                success=True,
                data=result,
                metadata={
                    "symbol": symbol,
                    "regime": regime,
                    "confidence": confidence,
                },
            )

        except Exception as e:
            logger.error("Failed to detect market trend", error=str(e), symbol=kwargs.get("symbol"))
            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                metadata={"symbol": kwargs.get("symbol")},
            )


class MarketRegimeDetectVolatilityTool(Tool):
    """Tool for detecting volatility regimes (high, normal, low).

    Uses rolling volatility calculations to classify volatility regimes.

    Why Rolling Volatility vs GARCH:
        While GARCH models are theoretically superior, we use rolling volatility because:
        - More stable on individual stocks (GARCH can be unstable)
        - Easier to explain and interpret
        - Less prone to overfitting on retail investment horizons
        - Robust and reliable for practical applications

    Current Implementation:
        - Rolling volatility using log-returns (simple moving average)
        - Classification using μ ± σ thresholds

    Future Improvements:
        - EWMA volatility (RiskMetrics style) for more responsive estimates
        - Percentile-based regimes (top 80% → high, bottom 20% → low) instead of μ ± σ

    Theoretical Foundation:
        - Andersen & Bollerslev (1998): Validates realized volatility models
        - RiskMetrics (J.P. Morgan, 1996): Rolling volatility methodology with annualization
        - Regime classification based on statistical deviation from historical mean
    """

    def __init__(self, market_data_provider: MarketDataProvider) -> None:
        """Initialize tool with market data provider.

        Args:
            market_data_provider: Provider for historical market data
        """
        self._provider = market_data_provider

    def get_name(self) -> str:
        """Get tool name."""
        return "detect_volatility_regime"

    def get_description(self) -> str:
        """Get tool description."""
        return (
            "Detect volatility regime (high, normal, or low) for a stock "
            "using rolling volatility analysis."
        )

    def get_schema(self) -> ToolSchema:
        """Get tool schema."""
        return ToolSchema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol (e.g., 'AAPL', 'MSFT')",
                    },
                    "lookback_days": {
                        "type": "integer",
                        "description": "Number of days to analyze for volatility detection",
                        "default": 252,
                    },
                    "volatility_window": {
                        "type": "integer",
                        "description": "Window size for volatility calculation (days)",
                        "default": 20,
                    },
                },
                "required": ["symbol"],
            },
            returns={
                "type": "object",
                "description": "Volatility regime detection results with classification and metrics",
            },
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute volatility regime detection tool."""
        try:
            validated = self.validate_parameters(**kwargs)
            symbol = validated["symbol"].upper()
            lookback_days = validated.get("lookback_days", 252)
            vol_window = validated.get("volatility_window", 20)

            # Get historical data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)

            historical_data = await self._provider.get_historical_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval="1d",
            )

            if not historical_data:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"No historical data available for {symbol}",
                    metadata={"symbol": symbol},
                )

            # Extract closing prices
            prices = [float(data.close_price) for data in historical_data]

            # Adapt volatility window based on available data
            if len(prices) < vol_window + 1:
                if len(prices) < 10:
                    return ToolResult(
                        success=False,
                        data=None,
                        error=(
                            f"Insufficient data for volatility analysis: need at least 10 data points, "
                            f"got {len(prices)}. This stock may be newly listed or have limited trading history."
                        ),
                        metadata={
                            "symbol": symbol,
                            "data_points": len(prices),
                            "suggestion": "Try a stock with more trading history, or use a shorter lookback period.",
                        },
                    )
                # Adjust volatility window to fit available data
                adjusted_vol_window = max(5, len(prices) - 5)
                vol_window = adjusted_vol_window
                logger.warning(
                    "Adjusted volatility window due to limited data",
                    symbol=symbol,
                    data_points=len(prices),
                    adjusted_vol_window=vol_window,
                )

            # Calculate volatility using rolling window (simple moving average)
            # Future: Can switch to _calculate_ewma_volatility() for RiskMetrics-style EWMA
            volatility_values = _calculate_volatility(prices, window=vol_window)

            # Filter out None values for analysis
            valid_vols = [v for v in volatility_values if v is not None]
            if not valid_vols:
                return ToolResult(
                    success=False,
                    data=None,
                    error="Could not calculate volatility from available data",
                    metadata={"symbol": symbol},
                )

            current_vol = valid_vols[-1]
            mean_vol = sum(valid_vols) / len(valid_vols)

            # Classify regime using μ ± σ thresholds
            # Future: Can switch to _classify_volatility_regime_percentile() for percentile-based classification
            regime = _classify_volatility_regime(current_vol, valid_vols)

            # Calculate additional metrics
            max_vol = max(valid_vols)
            min_vol = min(valid_vols)
            vol_percentile = sum(1 for v in valid_vols if v <= current_vol) / len(valid_vols) * 100

            # Check if parameters were adjusted
            original_vol_window = validated.get("volatility_window", 20)
            parameters_adjusted = vol_window != original_vol_window

            result = {
                "symbol": symbol,
                "regime": regime,
                "current_volatility": round(current_vol * 100, 2),  # As percentage
                "mean_volatility": round(mean_vol * 100, 2),
                "max_volatility": round(max_vol * 100, 2),
                "min_volatility": round(min_vol * 100, 2),
                "volatility_percentile": round(vol_percentile, 2),
                "analysis_period_days": lookback_days,
                "volatility_window": vol_window,
                "data_points": len(prices),
                "parameters_adjusted": parameters_adjusted,
            }

            if parameters_adjusted:
                result["note"] = (
                    f"Analysis adapted for limited data history. "
                    f"Used volatility window: {vol_window} (requested: {original_vol_window}). "
                    f"Results may have lower confidence."
                )

            return ToolResult(
                success=True,
                data=result,
                metadata={
                    "symbol": symbol,
                    "regime": regime,
                    "current_volatility_pct": round(current_vol * 100, 2),
                },
            )

        except Exception as e:
            logger.error(
                "Failed to detect volatility regime",
                error=str(e),
                symbol=kwargs.get("symbol"),
            )
            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                metadata={"symbol": kwargs.get("symbol")},
            )


class MarketRegimeDetectCyclesTool(Tool):
    """Tool for detecting market cycles and regime transitions.

    Identifies different phases of market cycles and potential regime changes.

    Theoretical Foundation:
        - Hamilton (1989): Regime switching models for nonstationary time series
        - Wyckoff Method (1930s, modernized): Accumulation/Markup/Distribution/Markdown phases
        - Lo (2004): Adaptive Markets Hypothesis - explains why regimes exist and change
    """

    def __init__(self, market_data_provider: MarketDataProvider) -> None:
        """Initialize tool with market data provider.

        Args:
            market_data_provider: Provider for historical market data
        """
        self._provider = market_data_provider

    def get_name(self) -> str:
        """Get tool name."""
        return "detect_market_cycles"

    def get_description(self) -> str:
        """Get tool description."""
        return (
            "Detect market cycles and regime transitions for a stock. "
            "Identifies accumulation, markup, distribution, and markdown phases."
        )

    def get_schema(self) -> ToolSchema:
        """Get tool schema."""
        return ToolSchema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol (e.g., 'AAPL', 'MSFT')",
                    },
                    "lookback_days": {
                        "type": "integer",
                        "description": "Number of days to analyze for cycle detection",
                        "default": 252,
                    },
                },
                "required": ["symbol"],
            },
            returns={
                "type": "object",
                "description": "Market cycle detection results with phase identification",
            },
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute market cycle detection tool."""
        try:
            validated = self.validate_parameters(**kwargs)
            symbol = validated["symbol"].upper()
            lookback_days = validated.get("lookback_days", 252)

            # Get historical data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days)

            historical_data = await self._provider.get_historical_data(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                interval="1d",
            )

            if not historical_data:
                return ToolResult(
                    success=False,
                    data=None,
                    error=f"No historical data available for {symbol}",
                    metadata={"symbol": symbol},
                )

            # Extract prices and volumes
            prices = [float(data.close_price) for data in historical_data]
            volumes = [data.volume for data in historical_data]

            # Adapt analysis parameters based on available data
            if len(prices) < 50:
                if len(prices) < 20:
                    return ToolResult(
                        success=False,
                        data=None,
                        error=(
                            f"Insufficient data for cycle analysis: need at least 20 data points, "
                            f"got {len(prices)}. This stock may be newly listed or have limited trading history."
                        ),
                        metadata={
                            "symbol": symbol,
                            "data_points": len(prices),
                            "suggestion": "Try a stock with more trading history, or use a shorter lookback period.",
                        },
                    )
                # Use smaller MAs for limited data
                ma_short_period = max(5, len(prices) // 4)
                ma_long_period = max(ma_short_period + 5, len(prices) - 5)
                logger.warning(
                    "Adjusted cycle detection parameters due to limited data",
                    symbol=symbol,
                    data_points=len(prices),
                    ma_short_period=ma_short_period,
                    ma_long_period=ma_long_period,
                )
            else:
                ma_short_period = 20
                ma_long_period = 50

            # Calculate moving averages for trend
            ma_20 = _calculate_moving_average(prices, ma_short_period)
            ma_50 = _calculate_moving_average(prices, ma_long_period)

            current_price = prices[-1]
            current_ma20 = ma_20[-1]
            current_ma50 = ma_50[-1]

            # Calculate price position relative to range
            price_range = max(prices) - min(prices)
            price_position = (
                ((current_price - min(prices)) / price_range * 100) if price_range > 0 else 50
            )

            # Calculate volume trend (adapt window to available data)
            volume_window = min(20, len(volumes) // 2)
            recent_volume = (
                sum(volumes[-volume_window:]) / volume_window
                if len(volumes) >= volume_window
                else volumes[-1]
            )
            avg_volume = sum(volumes) / len(volumes)
            volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1.0

            # Determine cycle phase using Wyckoff Method (1930s, modernized)
            # Phase definitions:
            # - Accumulation: price near lows, low volume, starting to rise (smart money buying)
            # - Markup: price rising, increasing volume, above MAs (public participation)
            # - Distribution: price near highs, high volume, starting to decline (smart money selling)
            # - Markdown: price falling, decreasing volume, below MAs (public selling)
            # Based on Hamilton (1989) regime switching and Lo (2004) adaptive markets

            if current_ma20 and current_ma50:
                if current_price > current_ma20 > current_ma50 and price_position > 60:
                    if volume_ratio > 1.2:
                        phase = "markup"
                        phase_description = "Strong uptrend with high volume - bullish phase"
                    else:
                        phase = "markup"
                        phase_description = "Uptrend with moderate volume - bullish phase"
                elif current_price < current_ma20 < current_ma50 and price_position < 40:
                    if volume_ratio > 1.2:
                        phase = "markdown"
                        phase_description = "Strong downtrend with high volume - bearish phase"
                    else:
                        phase = "markdown"
                        phase_description = "Downtrend with moderate volume - bearish phase"
                elif price_position > 70 and volume_ratio > 1.1:
                    phase = "distribution"
                    phase_description = "Price near highs with elevated volume - potential top"
                elif price_position < 30 and volume_ratio < 0.9:
                    phase = "accumulation"
                    phase_description = "Price near lows with low volume - potential bottom"
                else:
                    phase = "transition"
                    phase_description = "Transition phase - unclear direction"
            else:
                phase = "transition"
                phase_description = "Insufficient data for cycle detection"

            # Detect potential regime change (use actual periods)
            recent_period = min(ma_short_period, len(prices) - 1)
            longer_period = min(ma_long_period, len(prices) - 1)
            recent_trend = (
                "up"
                if prices[-1] > prices[-recent_period]
                else "down" if len(prices) > recent_period else "neutral"
            )
            longer_trend = (
                "up"
                if prices[-1] > prices[-longer_period]
                else "down" if len(prices) > longer_period else "neutral"
            )
            regime_change_signal = recent_trend != longer_trend

            # Check if parameters were adjusted
            parameters_adjusted = ma_short_period != 20 or ma_long_period != 50

            result = {
                "symbol": symbol,
                "current_phase": phase,
                "phase_description": phase_description,
                "price_position_pct": round(price_position, 2),
                "volume_ratio": round(volume_ratio, 2),
                "current_price": round(current_price, 2),
                "ma_20": round(current_ma20, 2) if current_ma20 else None,
                "ma_50": round(current_ma50, 2) if current_ma50 else None,
                "recent_trend": recent_trend,
                "longer_trend": longer_trend,
                "potential_regime_change": regime_change_signal,
                "analysis_period_days": lookback_days,
                "data_points": len(prices),
                "parameters_adjusted": parameters_adjusted,
                "ma_short_period_used": ma_short_period,
                "ma_long_period_used": ma_long_period,
            }

            if parameters_adjusted:
                result["note"] = (
                    f"Analysis adapted for limited data history. "
                    f"Used MA periods: {ma_short_period}/{ma_long_period} (standard: 20/50). "
                    f"Results may have lower confidence."
                )

            return ToolResult(
                success=True,
                data=result,
                metadata={
                    "symbol": symbol,
                    "phase": phase,
                    "regime_change_signal": regime_change_signal,
                },
            )

        except Exception as e:
            logger.error(
                "Failed to detect market cycles", error=str(e), symbol=kwargs.get("symbol")
            )
            return ToolResult(
                success=False,
                data=None,
                error=str(e),
                metadata={"symbol": kwargs.get("symbol")},
            )


def create_rule_based_regime_tools(
    market_data_provider: MarketDataProvider,
) -> list[Tool]:
    """Create all rule-based market regime detection tools.

    Args:
        market_data_provider: Market data provider instance

    Returns:
        List of rule-based market regime detection tools
    """
    return [
        MarketRegimeDetectTrendTool(market_data_provider),
        MarketRegimeDetectVolatilityTool(market_data_provider),
        MarketRegimeDetectCyclesTool(market_data_provider),
    ]


# Backward compatibility alias
create_market_regime_tools = create_rule_based_regime_tools
