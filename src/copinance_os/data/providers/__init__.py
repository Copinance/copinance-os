"""Data provider implementations.

In pure engine mode (default for library callers), copinance-os uses
``FactBasedMarketProvider`` or ``NullMarketDataProvider``, never initiating
un-governed scraping or network calls. Standalone CLI workflows explicitly opt
into vendor adapters (``YFinanceMarketProvider``, ``FredMacroeconomicProvider``, etc.).
"""

from copinance_os.data.providers.facts import (
    FactBasedMacroProvider,
    FactBasedMarketProvider,
    FactNotFound,
    FactProviderNotConfigured,
    MarketFacts,
    NullFundamentalDataProvider,
    NullMacroDataProvider,
    NullMarketDataProvider,
)
from copinance_os.data.providers.fred import FredMacroeconomicProvider
from copinance_os.data.providers.sec import EdgarToolsFundamentalProvider
from copinance_os.data.providers.yfinance import (
    YFinanceFundamentalProvider,
    YFinanceMarketProvider,
)

__all__ = [
    "EdgarToolsFundamentalProvider",
    "FactBasedMacroProvider",
    "FactBasedMarketProvider",
    "FactNotFound",
    "FactProviderNotConfigured",
    "FredMacroeconomicProvider",
    "MarketFacts",
    "NullFundamentalDataProvider",
    "NullMacroDataProvider",
    "NullMarketDataProvider",
    "YFinanceFundamentalProvider",
    "YFinanceMarketProvider",
]
