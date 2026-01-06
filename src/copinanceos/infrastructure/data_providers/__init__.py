"""Data provider implementations.

This module contains implementations of data provider interfaces.
Developers can easily add their own providers by implementing the interfaces
defined in `copinanceos.domain.ports.data_providers`.
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
