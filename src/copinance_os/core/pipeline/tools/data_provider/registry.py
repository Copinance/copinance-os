"""Registry and factory functions for data provider tools."""

from typing import Any

from copinance_os.core.pipeline.tools.data_provider.fundamental_data import (
    FundamentalDataFindSecFundsTool,
    FundamentalDataGetFinancialStatementsTool,
    FundamentalDataGetFundamentalsTool,
    FundamentalDataGetSEC13FInstitutionalHoldingsTool,
    FundamentalDataGetSECCompanyEdgarProfileTool,
    FundamentalDataGetSECCompanyFactsStatementTool,
    FundamentalDataGetSECCompareFinancialsTool,
    FundamentalDataGetSECFilingContentTool,
    FundamentalDataGetSECFilingsTool,
    FundamentalDataGetSecFundEntityTool,
    FundamentalDataGetSecFundFilingsTool,
    FundamentalDataGetSecFundLatestReportTool,
    FundamentalDataGetSecFundPortfolioTool,
    FundamentalDataGetSECInsiderForm4Tool,
    FundamentalDataGetSECXbrlStatementTableTool,
)
from copinance_os.core.pipeline.tools.data_provider.market_data import (
    MarketDataGetHistoricalDataTool,
    MarketDataGetOptionsChainTool,
    MarketDataGetQuoteTool,
    MarketDataOptionsPositioningTool,
    MarketDataSearchInstrumentsTool,
)
from copinance_os.core.pipeline.tools.data_provider.provider_selector import (
    MultiProviderSelector,
    ProviderSelector,
)
from copinance_os.domain.ports.data_providers import (
    FundamentalDataProvider,
    MarketDataProvider,
)
from copinance_os.domain.ports.tools import Tool


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
        MarketDataSearchInstrumentsTool(provider, cache_manager=cache_manager),
        MarketDataGetOptionsChainTool(provider, cache_manager=cache_manager),
        MarketDataOptionsPositioningTool(provider, cache_manager=cache_manager),
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

    # Order matters for LLM prompts: analytical SEC tools before generic filing list/content.
    return [
        FundamentalDataGetFundamentalsTool(actual_provider, cache_manager=cache_manager),
        FundamentalDataGetSECCompanyEdgarProfileTool(provider, cache_manager=cache_manager),
        FundamentalDataFindSecFundsTool(provider, cache_manager=cache_manager),
        FundamentalDataGetSecFundEntityTool(provider, cache_manager=cache_manager),
        FundamentalDataGetSecFundFilingsTool(provider, cache_manager=cache_manager),
        FundamentalDataGetSecFundPortfolioTool(provider, cache_manager=cache_manager),
        FundamentalDataGetSecFundLatestReportTool(provider, cache_manager=cache_manager),
        FundamentalDataGetSECCompanyFactsStatementTool(provider, cache_manager=cache_manager),
        FundamentalDataGetSECCompareFinancialsTool(provider, cache_manager=cache_manager),
        FundamentalDataGetFinancialStatementsTool(actual_provider, cache_manager=cache_manager),
        FundamentalDataGetSECXbrlStatementTableTool(provider, cache_manager=cache_manager),
        FundamentalDataGetSECInsiderForm4Tool(provider, cache_manager=cache_manager),
        FundamentalDataGetSEC13FInstitutionalHoldingsTool(provider, cache_manager=cache_manager),
        FundamentalDataGetSECFilingsTool(provider, cache_manager=cache_manager),
        FundamentalDataGetSECFilingContentTool(provider, cache_manager=cache_manager),
    ]


def create_fundamental_data_tools_with_providers(
    default_provider: FundamentalDataProvider,
    sec_filings_provider: FundamentalDataProvider | None = None,
    cache_manager: Any | None = None,  # CacheManager type, avoiding circular import
) -> list[Tool]:
    """Create fundamental data tools with provider selection.

    This function allows different providers for different tools:
    - Default provider for fundamentals and financial statements
    - Optional separate provider for SEC filings

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
            FundamentalDataGetSECCompanyEdgarProfileTool(
                multi_selector, cache_manager=cache_manager
            ),
            FundamentalDataFindSecFundsTool(multi_selector, cache_manager=cache_manager),
            FundamentalDataGetSecFundEntityTool(multi_selector, cache_manager=cache_manager),
            FundamentalDataGetSecFundFilingsTool(multi_selector, cache_manager=cache_manager),
            FundamentalDataGetSecFundPortfolioTool(multi_selector, cache_manager=cache_manager),
            FundamentalDataGetSecFundLatestReportTool(multi_selector, cache_manager=cache_manager),
            FundamentalDataGetSECCompanyFactsStatementTool(
                multi_selector, cache_manager=cache_manager
            ),
            FundamentalDataGetSECCompareFinancialsTool(multi_selector, cache_manager=cache_manager),
            FundamentalDataGetFinancialStatementsTool(
                default_provider, cache_manager=cache_manager
            ),
            FundamentalDataGetSECXbrlStatementTableTool(
                multi_selector, cache_manager=cache_manager
            ),
            FundamentalDataGetSECInsiderForm4Tool(multi_selector, cache_manager=cache_manager),
            FundamentalDataGetSEC13FInstitutionalHoldingsTool(
                multi_selector, cache_manager=cache_manager
            ),
            FundamentalDataGetSECFilingsTool(multi_selector, cache_manager=cache_manager),
            FundamentalDataGetSECFilingContentTool(multi_selector, cache_manager=cache_manager),
        ]
    else:
        # Use single provider for all tools
        return create_fundamental_data_tools(default_provider, cache_manager=cache_manager)
