"""Market access composition (e.g. vendor provider + derived option analytics).

Vendor integrations live under ``infrastructure.data_providers`` only.
"""

from copinance_os.data.providers.market.option_analytics_market_data_provider import (
    OptionAnalyticsMarketDataProvider,
)

__all__ = ["OptionAnalyticsMarketDataProvider"]
