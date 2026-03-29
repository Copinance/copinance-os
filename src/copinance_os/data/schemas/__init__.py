"""Pydantic schemas for normalized data at provider boundaries.

Domain entities remain in ``copinance_os.domain.models``. Use this package for
ingestion-specific DTOs (e.g. raw provider payloads) when you need a dedicated
contract separate from domain entities.
"""

from copinance_os.data.schemas.market_data_conversions import (
    CoerceMarketDataPointsResult,
    coerce_sorted_market_data_points,
    coerce_sorted_market_data_points_detailed,
    price_series_from_market_data_points,
)
from copinance_os.data.schemas.price_series import PriceSeries

__all__ = [
    "CoerceMarketDataPointsResult",
    "PriceSeries",
    "coerce_sorted_market_data_points",
    "coerce_sorted_market_data_points_detailed",
    "price_series_from_market_data_points",
]
