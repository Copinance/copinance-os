"""Analysis tools for market analysis.

This module provides tools for analyzing market data, including market regime detection,
technical analysis, and other analytical functions.
"""

from copinance_os.core.pipeline.tools.analysis.market_regime import (
    MacroRegimeIndicatorsTool,
    MarketRegimeDetectCyclesTool,
    MarketRegimeDetectTrendTool,
    MarketRegimeDetectVolatilityTool,
    MarketRegimeIndicatorsTool,
    create_macro_regime_indicators_tool,
    create_rule_based_regime_tools,
)
from copinance_os.core.pipeline.tools.analysis.market_regime.registry import (
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
    "create_rule_based_regime_tools",
    # Registry functions
    "create_all_regime_tools",
    "create_regime_tools_by_type",
]
