"""Registry and factory functions for market regime detection tools.

This module provides factory functions to create regime detection tools using
different methodologies (rule-based, statistical, etc.) and allows combining
them in a unified registry.
"""

from typing import Literal

from copinanceos.domain.ports.data_providers import MarketDataProvider
from copinanceos.domain.ports.tools import Tool
from copinanceos.infrastructure.tools.analysis.market_regime.rule_based import (
    create_rule_based_regime_tools,
)
from copinanceos.infrastructure.tools.analysis.market_regime.statistical import (
    create_statistical_regime_tools,
)


def create_all_regime_tools(
    market_data_provider: MarketDataProvider,
    methods: list[Literal["rule_based", "statistical"]] | None = None,
) -> list[Tool]:
    """Create regime detection tools using specified methods.

    Args:
        market_data_provider: Market data provider instance
        methods: List of methods to use. If None, defaults to ["rule_based"].
                 Options: "rule_based", "statistical"

    Returns:
        Combined list of regime detection tools from all specified methods

    Example:
        ```python
        # Get only rule-based tools (default)
        tools = create_all_regime_tools(provider)

        # Get both rule-based and statistical tools
        tools = create_all_regime_tools(provider, methods=["rule_based", "statistical"])

        # Get only statistical tools
        tools = create_all_regime_tools(provider, methods=["statistical"])
        ```
    """
    if methods is None:
        methods = ["rule_based"]

    tools: list[Tool] = []

    if "rule_based" in methods:
        tools.extend(create_rule_based_regime_tools(market_data_provider))

    if "statistical" in methods:
        tools.extend(create_statistical_regime_tools(market_data_provider))

    return tools


def create_regime_tools_by_type(
    market_data_provider: MarketDataProvider,
    method: Literal["rule_based", "statistical"],
) -> list[Tool]:
    """Create regime detection tools for a specific method type.

    Args:
        market_data_provider: Market data provider instance
        method: Method type ("rule_based" or "statistical")

    Returns:
        List of regime detection tools for the specified method

    Raises:
        ValueError: If method is not recognized
    """
    if method == "rule_based":
        return create_rule_based_regime_tools(market_data_provider)
    elif method == "statistical":
        return create_statistical_regime_tools(market_data_provider)
    else:
        raise ValueError(f"Unknown method: {method}. Use 'rule_based' or 'statistical'")
