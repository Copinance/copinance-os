"""Normalize provider outputs to ``PriceSeries`` and sorted point lists."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import structlog

from copinance_os.data.schemas.price_series import PriceSeries
from copinance_os.domain.models.market import MarketDataPoint

logger = structlog.get_logger(__name__)


def coerce_sorted_market_data_points(data_points: Sequence[Any]) -> list[MarketDataPoint]:
    """Coerce mixed points to ``MarketDataPoint`` and sort by timestamp (oldest first)."""
    out: list[MarketDataPoint] = []
    for p in data_points:
        if isinstance(p, MarketDataPoint):
            out.append(p)
        elif isinstance(p, dict):
            try:
                out.append(MarketDataPoint.model_validate(p))
            except Exception as e:
                logger.debug("skip_invalid_market_point", error=str(e))
    return sorted(out, key=lambda x: x.timestamp)


def price_series_from_market_data_points(points: Sequence[MarketDataPoint]) -> PriceSeries:
    """Build a chronologically ordered close series from OHLCV points."""
    if not points:
        raise ValueError("Cannot build PriceSeries from empty market data")
    ordered = sorted(points, key=lambda p: p.timestamp)
    closes = [float(p.close_price) for p in ordered]
    timestamps = [p.timestamp for p in ordered]
    return PriceSeries(closes=closes, timestamps=timestamps)
