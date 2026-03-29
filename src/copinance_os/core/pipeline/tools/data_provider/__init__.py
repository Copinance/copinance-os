"""Data provider tools module.

This module provides tools that wrap data provider methods for use with LLMs
and other tool-based systems. Tools are organized by data provider type.
"""

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
    MarketDataSearchInstrumentsTool,
)
from copinance_os.core.pipeline.tools.data_provider.registry import (
    DataProviderToolRegistry,
    create_fundamental_data_tools,
    create_fundamental_data_tools_with_providers,
    create_market_data_tools,
)

__all__ = [
    # Market data tools
    "MarketDataGetQuoteTool",
    "MarketDataGetHistoricalDataTool",
    "MarketDataSearchInstrumentsTool",
    "MarketDataGetOptionsChainTool",
    # Fundamental data tools
    "FundamentalDataGetFundamentalsTool",
    "FundamentalDataGetFinancialStatementsTool",
    "FundamentalDataGetSECFilingsTool",
    "FundamentalDataGetSECFilingContentTool",
    "FundamentalDataGetSECCompanyFactsStatementTool",
    "FundamentalDataGetSECCompareFinancialsTool",
    "FundamentalDataGetSECXbrlStatementTableTool",
    "FundamentalDataGetSECInsiderForm4Tool",
    "FundamentalDataGetSEC13FInstitutionalHoldingsTool",
    "FundamentalDataGetSECCompanyEdgarProfileTool",
    "FundamentalDataFindSecFundsTool",
    "FundamentalDataGetSecFundEntityTool",
    "FundamentalDataGetSecFundFilingsTool",
    "FundamentalDataGetSecFundPortfolioTool",
    "FundamentalDataGetSecFundLatestReportTool",
    # Factory functions
    "create_market_data_tools",
    "create_fundamental_data_tools",
    "create_fundamental_data_tools_with_providers",
    # Registry
    "DataProviderToolRegistry",
]
