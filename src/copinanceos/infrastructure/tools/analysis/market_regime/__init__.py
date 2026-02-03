"""Market regime detection tools for stock analysis.

This package provides tools for detecting different market regimes using various methodologies:
- Rule-based detection: Technical indicators, moving averages, thresholds
- Statistical inference: Hidden Markov Models (HMM), Regime Switching Models (Hamilton), etc.

The package is organized to allow easy extension with new detection methods while maintaining
a consistent interface for all regime detection tools.
"""

from copinanceos.infrastructure.tools.analysis.market_regime.indicators import (
    MarketRegimeIndicatorsTool,
    create_market_regime_indicators_tool,
)
from copinanceos.infrastructure.tools.analysis.market_regime.macro_indicators import (
    MacroRegimeIndicatorsTool,
    create_macro_regime_indicators_tool,
)
from copinanceos.infrastructure.tools.analysis.market_regime.rule_based import (
    MarketRegimeDetectCyclesTool,
    MarketRegimeDetectTrendTool,
    MarketRegimeDetectVolatilityTool,
    create_rule_based_regime_tools,
)

__all__ = [
    "MarketRegimeDetectTrendTool",
    "MarketRegimeDetectVolatilityTool",
    "MarketRegimeDetectCyclesTool",
    "create_rule_based_regime_tools",
    "MarketRegimeIndicatorsTool",
    "create_market_regime_indicators_tool",
    "MacroRegimeIndicatorsTool",
    "create_macro_regime_indicators_tool",
]
