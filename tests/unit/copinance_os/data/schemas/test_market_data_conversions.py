"""Tests for market data → ``PriceSeries`` conversion."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from copinance_os.data.schemas.market_data_conversions import (
    coerce_sorted_market_data_points,
    price_series_from_market_data_points,
)
from copinance_os.data.schemas.price_series import PriceSeries
from copinance_os.domain.models.market import MarketDataPoint


def _point(ts: datetime, close: float) -> MarketDataPoint:
    d = Decimal(str(close))
    return MarketDataPoint(
        symbol="SPY",
        timestamp=ts,
        open_price=d,
        close_price=d,
        high_price=d,
        low_price=d,
        volume=1_000_000,
    )


@pytest.mark.unit
def test_coerce_sorts_by_timestamp() -> None:
    t0 = datetime(2024, 1, 2, tzinfo=UTC)
    t1 = datetime(2024, 1, 1, tzinfo=UTC)
    raw = [
        _point(t0, 100.0).model_dump(mode="json"),
        _point(t1, 99.0).model_dump(mode="json"),
    ]
    out = coerce_sorted_market_data_points(raw)
    assert [p.timestamp for p in out][0] == t1


@pytest.mark.unit
def test_price_series_from_points() -> None:
    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    t1 = datetime(2024, 1, 2, tzinfo=UTC)
    ps = price_series_from_market_data_points([_point(t1, 101.0), _point(t0, 100.0)])
    assert ps.closes == [100.0, 101.0]
    assert ps.timestamps is not None and len(ps.timestamps) == 2


@pytest.mark.unit
def test_price_series_rejects_mismatched_timestamps() -> None:
    with pytest.raises(ValueError, match="same length"):
        PriceSeries(closes=[1.0, 2.0], timestamps=[datetime.now(UTC)])
