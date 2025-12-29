"""Registry and factory functions for data provider tools."""

from typing import Any

from copinanceos.domain.ports.data_providers import (
    FundamentalDataProvider,
    MarketDataProvider,
)
from copinanceos.domain.ports.tools import Tool
from copinanceos.infrastructure.tools.analysis import create_market_regime_tools
from copinanceos.infrastructure.tools.data_provider.fundamental_data import (
    FundamentalDataGetFinancialStatementsTool,
    FundamentalDataGetFundamentalsTool,
    FundamentalDataGetSECFilingContentTool,
    FundamentalDataGetSECFilingsTool,
)
from copinanceos.infrastructure.tools.data_provider.market_data import (
    MarketDataGetHistoricalDataTool,
    MarketDataGetQuoteTool,
    MarketDataSearchStocksTool,
)
from copinanceos.infrastructure.tools.data_provider.provider_selector import (
    MultiProviderSelector,
    ProviderSelector,
)
from copinanceos.infrastructure.tools.tool_registry import ToolRegistry


def create_market_data_tools(
    provider: MarketDataProvider,
    cache_manager: Any | None = None,  # CacheManager type, avoiding circular import
) -> list[Tool]:
    """Create all market data tools for a provider.

    Args:
        provider: Market data provider instance
        cache_manager: Optional cache manager for caching tool results

    Returns:
        List of market data tools
    """
    return [
        MarketDataGetQuoteTool(provider, cache_manager=cache_manager),
        MarketDataGetHistoricalDataTool(provider, cache_manager=cache_manager),
        MarketDataSearchStocksTool(provider, cache_manager=cache_manager),
    ]


def create_fundamental_data_tools(
    provider: (
        FundamentalDataProvider
        | ProviderSelector[FundamentalDataProvider]
        | MultiProviderSelector[FundamentalDataProvider]
    ),
    cache_manager: Any | None = None,  # CacheManager type, avoiding circular import
) -> list[Tool]:
    """Create all fundamental data tools for a provider or provider selector.

    Args:
        provider: Fundamental data provider instance, ProviderSelector, or MultiProviderSelector.
                 If MultiProviderSelector, SEC filings tool will use provider with 'sec_filings' capability.

    Returns:
        List of fundamental data tools
    """
    # Extract actual provider for tools that don't support selectors
    actual_provider: FundamentalDataProvider
    if isinstance(provider, (ProviderSelector, MultiProviderSelector)):
        if isinstance(provider, MultiProviderSelector):
            default_provider = provider.get_default_provider()
            if default_provider is None:
                raise ValueError("No default provider available in MultiProviderSelector")
            actual_provider = default_provider
        else:
            actual_provider = provider.get_provider()
    else:
        actual_provider = provider

    return [
        FundamentalDataGetFundamentalsTool(actual_provider, cache_manager=cache_manager),
        FundamentalDataGetFinancialStatementsTool(actual_provider, cache_manager=cache_manager),
        FundamentalDataGetSECFilingsTool(
            provider, cache_manager=cache_manager
        ),  # SEC filings tool supports selectors
        FundamentalDataGetSECFilingContentTool(
            provider, cache_manager=cache_manager
        ),  # SEC filing content tool supports selectors
    ]


def create_fundamental_data_tools_with_providers(
    default_provider: FundamentalDataProvider,
    sec_filings_provider: FundamentalDataProvider | None = None,
    cache_manager: Any | None = None,  # CacheManager type, avoiding circular import
) -> list[Tool]:
    """Create fundamental data tools with provider selection.

    This function allows different providers for different tools:
    - Default provider for fundamentals and financial statements
    - Optional separate provider for SEC filings (e.g., EDGAR)

    Args:
        default_provider: Provider for fundamentals and financial statements
        sec_filings_provider: Optional provider specifically for SEC filings.
                             If None, uses default_provider.

    Returns:
        List of fundamental data tools with appropriate provider selection
    """
    if sec_filings_provider and sec_filings_provider != default_provider:
        # Use MultiProviderSelector to route SEC filings to specific provider
        multi_selector = MultiProviderSelector[FundamentalDataProvider]()
        multi_selector.register_provider("default", default_provider)
        multi_selector.register_provider(
            "sec_filings", sec_filings_provider, capabilities=["sec_filings"]
        )

        return [
            FundamentalDataGetFundamentalsTool(default_provider, cache_manager=cache_manager),
            FundamentalDataGetFinancialStatementsTool(
                default_provider, cache_manager=cache_manager
            ),
            FundamentalDataGetSECFilingsTool(multi_selector, cache_manager=cache_manager),
            FundamentalDataGetSECFilingContentTool(multi_selector, cache_manager=cache_manager),
        ]
    else:
        # Use single provider for all tools
        return create_fundamental_data_tools(default_provider, cache_manager=cache_manager)


class DataProviderToolRegistry:
    """Convenience registry that automatically creates tools from data providers."""

    def __init__(
        self,
        market_data_provider: MarketDataProvider | None = None,
        fundamental_data_provider: FundamentalDataProvider | None = None,
    ) -> None:
        """Initialize registry with data providers.

        Args:
            market_data_provider: Optional market data provider
            fundamental_data_provider: Optional fundamental data provider
        """
        self._registry: ToolRegistry = ToolRegistry()

        if market_data_provider:
            tools = create_market_data_tools(market_data_provider)
            self._registry.register_many(tools)
            # Also register market regime detection tools
            regime_tools = create_market_regime_tools(market_data_provider)
            self._registry.register_many(regime_tools)

        if fundamental_data_provider:
            tools = create_fundamental_data_tools(fundamental_data_provider)
            self._registry.register_many(tools)

    def get_registry(self) -> ToolRegistry:
        """Get the underlying tool registry.

        Returns:
            ToolRegistry instance
        """
        return self._registry

    def register_tool(self, tool: Tool) -> None:
        """Register an additional tool.

        Args:
            tool: Tool to register
        """
        self._registry.register(tool)
