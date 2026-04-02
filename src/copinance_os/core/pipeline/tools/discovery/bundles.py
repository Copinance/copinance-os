"""Concrete tool bundle factories (delegate to existing create_* helpers)."""

from copinance_os.core.pipeline.tools.analysis import (
    create_macro_regime_indicators_tool,
    create_rule_based_regime_tools,
)
from copinance_os.core.pipeline.tools.analysis.market_regime.indicators import (
    create_market_regime_indicators_tool,
)
from copinance_os.core.pipeline.tools.data_provider.registry import (
    create_fundamental_data_tools,
    create_fundamental_data_tools_with_providers,
    create_market_data_tools,
)
from copinance_os.domain.models.tool_bundle_context import ToolBundleContext
from copinance_os.domain.ports.tools import Tool


def market_data_tools_bundle(ctx: ToolBundleContext) -> list[Tool]:
    """OHLCV, quote, search, options chain tools."""
    if ctx.market_data_provider is None:
        return []
    return create_market_data_tools(ctx.market_data_provider, cache_manager=ctx.cache_manager)


def rule_based_regime_tools_bundle(ctx: ToolBundleContext) -> list[Tool]:
    """Rule-based trend / volatility / cycle regime tools."""
    if ctx.market_data_provider is None:
        return []
    return create_rule_based_regime_tools(ctx.market_data_provider)


def market_regime_indicators_bundle(ctx: ToolBundleContext) -> list[Tool]:
    """VIX, breadth, sector rotation indicators tool (single tool)."""
    if ctx.market_data_provider is None:
        return []
    return [
        create_market_regime_indicators_tool(
            ctx.market_data_provider,
            cache_manager=ctx.cache_manager,
        )
    ]


def macro_regime_indicators_bundle(ctx: ToolBundleContext) -> list[Tool]:
    """Macro (FRED) regime indicators tool when macro provider is configured."""
    if ctx.macro_data_provider is None or ctx.market_data_provider is None:
        return []
    return [
        create_macro_regime_indicators_tool(
            ctx.macro_data_provider,
            ctx.market_data_provider,
            cache_manager=ctx.cache_manager,
        )
    ]


def fundamental_data_tools_bundle(ctx: ToolBundleContext) -> list[Tool]:
    """Fundamental + SEC tools; respects optional ``sec_filings_provider`` split."""
    if ctx.fundamental_data_provider is None:
        return []
    if ctx.sec_filings_provider:
        return create_fundamental_data_tools_with_providers(
            default_provider=ctx.fundamental_data_provider,
            sec_filings_provider=ctx.sec_filings_provider,
            cache_manager=ctx.cache_manager,
        )
    return create_fundamental_data_tools(
        ctx.fundamental_data_provider,
        cache_manager=ctx.cache_manager,
    )
