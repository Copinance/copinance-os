"""Base classes and interfaces for market regime detection tools.

This module provides common abstractions for different regime detection methodologies,
allowing rule-based and statistical methods to share a consistent interface.
"""

from abc import ABC, abstractmethod
from math import log
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from copinanceos.domain.ports.data_providers import MarketDataProvider
from copinanceos.domain.ports.tools import Tool, ToolResult


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

    # Convert to list with None for NaN values
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

    # Calculate log(P_t / P_{t-1}) = log(P_t) - log(P_{t-1})
    log_prices = pd.Series([log(p) if p > 0 else 0.0 for p in prices])
    log_returns = log_prices.diff()

    # Return as list, skipping first NaN value (first price has no previous price)
    return [float(val) if pd.notna(val) else 0.0 for val in log_returns[1:]]


class BaseRegimeDetectionTool(Tool, ABC):
    """Base class for market regime detection tools.

    Provides common functionality and interface for all regime detection methods,
    whether rule-based or statistical.
    """

    def __init__(self, market_data_provider: MarketDataProvider) -> None:
        """Initialize regime detection tool with market data provider.

        Args:
            market_data_provider: Provider for historical market data
        """
        self._provider = market_data_provider

    @abstractmethod
    def get_detection_method(self) -> str:
        """Get the detection method name (e.g., 'rule_based', 'hmm', 'hamilton').

        Returns:
            Method identifier string
        """
        pass

    @abstractmethod
    async def _detect_regime(self, symbol: str, **kwargs: Any) -> dict[str, Any]:
        """Perform the actual regime detection.

        This method should be implemented by subclasses with their specific
        detection logic (rule-based, statistical, etc.).

        Args:
            symbol: Stock ticker symbol
            **kwargs: Method-specific parameters

        Returns:
            Dictionary with regime detection results
        """
        pass

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute regime detection tool.

        This base implementation handles common concerns like validation,
        error handling, and result formatting. Subclasses implement _detect_regime
        with their specific logic.

        Args:
            **kwargs: Tool parameters

        Returns:
            ToolResult with regime detection outcome
        """
        # Common validation and execution logic can go here
        # Subclasses can override if needed
        return await self._execute_impl(**kwargs)

    @abstractmethod
    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        """Execute tool implementation.

        Subclasses must implement this with their specific execution logic.
        """
        pass


class RegimeDetectionResult:
    """Structured result from regime detection.

    Provides a common structure for regime detection results across different methods.
    """

    def __init__(
        self,
        symbol: str,
        regime: str,
        confidence: float | str,
        method: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Initialize regime detection result.

        Args:
            symbol: Stock symbol
            regime: Detected regime (e.g., "bull", "bear", "high_volatility")
            confidence: Confidence level (float 0-1 or string like "high"/"medium"/"low")
            method: Detection method used
            metadata: Additional method-specific metadata
        """
        self.symbol = symbol
        self.regime = regime
        self.confidence = confidence
        self.method = method
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary.

        Returns:
            Dictionary representation of the result
        """
        return {
            "symbol": self.symbol,
            "regime": self.regime,
            "confidence": self.confidence,
            "method": self.method,
            "metadata": self.metadata,
        }
