"""Analysis tools for stock research.

This module provides tools for analyzing stock data, including market regime detection,
technical analysis, and other analytical functions.
"""

from copinanceos.infrastructure.tools.analysis.market_regime import (
    MacroRegimeIndicatorsTool,
    MarketRegimeDetectCyclesTool,
    MarketRegimeDetectTrendTool,
    MarketRegimeDetectVolatilityTool,
    MarketRegimeIndicatorsTool,
    create_macro_regime_indicators_tool,
    create_market_regime_tools,
)
from copinanceos.infrastructure.tools.analysis.market_regime.registry import (
    create_all_regime_tools,
    create_regime_tools_by_type,
)

__all__ = [
    # Market regime tools (rule-based, current implementation)
    "MarketRegimeDetectTrendTool",
    "MarketRegimeDetectVolatilityTool",
    "MarketRegimeDetectCyclesTool",
    "MarketRegimeIndicatorsTool",
    "MacroRegimeIndicatorsTool",
    "create_macro_regime_indicators_tool",
    "create_market_regime_tools",  # Backward compatibility
    # Registry functions
    "create_all_regime_tools",
    "create_regime_tools_by_type",
]
