"""Explicit dependency bag for tool bundle factories (DI-friendly, domain-only types)."""

from dataclasses import dataclass
from typing import Any

from copinance_os.domain.ports.data_providers import (
    FundamentalDataProvider,
    MacroeconomicDataProvider,
    MarketDataProvider,
)


@dataclass
class ToolBundleContext:
    """Dependencies passed to each tool bundle factory.

    Factories return empty lists when required providers are missing, except
    fundamentals bundles which require ``fundamental_data_provider``.
    """

    market_data_provider: MarketDataProvider | None = None
    macro_data_provider: MacroeconomicDataProvider | None = None
    fundamental_data_provider: FundamentalDataProvider | None = None
    sec_filings_provider: FundamentalDataProvider | None = None
    cache_manager: Any = None
