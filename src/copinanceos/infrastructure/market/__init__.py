"""Market access composition (e.g. vendor provider + derived option analytics).

Vendor integrations live under ``infrastructure.data_providers`` only.
"""

from copinanceos.infrastructure.market.option_analytics_market_data_provider import (
    OptionAnalyticsMarketDataProvider,
)

__all__ = ["OptionAnalyticsMarketDataProvider"]
