"""Vendor data provider implementations (source integrations only).

For composing market access with derived option analytics (Greeks, etc.), see
``copinanceos.infrastructure.market`` and ``copinanceos.infrastructure.analytics``.
"""

from copinanceos.infrastructure.data_providers.edgar import EdgarFundamentalProvider
from copinanceos.infrastructure.data_providers.fred import FredMacroeconomicProvider
from copinanceos.infrastructure.data_providers.yfinance import (
    YFinanceFundamentalProvider,
    YFinanceMarketProvider,
)

__all__ = [
    "YFinanceMarketProvider",
    "YFinanceFundamentalProvider",
    "EdgarFundamentalProvider",
    "FredMacroeconomicProvider",
]
