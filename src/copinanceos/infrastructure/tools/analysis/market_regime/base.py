"""Base classes and interfaces for market regime detection tools.

This module provides common abstractions for different regime detection methodologies,
allowing rule-based and statistical methods to share a consistent interface.
"""

from abc import ABC, abstractmethod
from typing import Any

from copinanceos.domain.ports.data_providers import MarketDataProvider
from copinanceos.domain.ports.tools import Tool, ToolResult


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
