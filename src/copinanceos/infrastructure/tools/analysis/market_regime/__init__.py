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
from copinanceos.infrastructure.tools.analysis.market_regime.rule_based import (
    MarketRegimeDetectCyclesTool,
    MarketRegimeDetectTrendTool,
    MarketRegimeDetectVolatilityTool,
    create_rule_based_regime_tools,
)

# Re-export for backward compatibility
__all__ = [
    # Rule-based tools (current implementation)
    "MarketRegimeDetectTrendTool",
    "MarketRegimeDetectVolatilityTool",
    "MarketRegimeDetectCyclesTool",
    "create_rule_based_regime_tools",
    # Market regime indicators tool
    "MarketRegimeIndicatorsTool",
    "create_market_regime_indicators_tool",
    # Factory function (backward compatible)
    "create_market_regime_tools",
]

# Backward compatibility: default to rule-based tools
create_market_regime_tools = create_rule_based_regime_tools
