"""Tests for market data → ``PriceSeries`` conversion."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from copinance_os.data.schemas.market_data_conversions import (
    coerce_sorted_market_data_points,
    coerce_sorted_market_data_points_detailed,
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
def test_coerce_detailed_counts_skips() -> None:
    t0 = datetime(2024, 1, 1, tzinfo=UTC)
    bad_dict = {"symbol": "SPY", "timestamp": "not-a-date"}
    raw = [
        _point(t0, 100.0),
        bad_dict,
        "not-a-point",
    ]
    detailed = coerce_sorted_market_data_points_detailed(raw, strict=False)
    assert detailed.accepted_as_model == 1
    assert detailed.skipped_invalid_dict == 1
    assert detailed.skipped_unsupported_type == 1
    assert len(detailed.points) == 1


@pytest.mark.unit
def test_coerce_strict_invalid_dict() -> None:
    bad_dict = {"symbol": "SPY"}
    with pytest.raises(ValueError, match="Invalid market data point"):
        coerce_sorted_market_data_points_detailed([bad_dict], strict=True)


@pytest.mark.unit
def test_coerce_strict_unsupported_type() -> None:
    with pytest.raises(TypeError, match="Unsupported market data point"):
        coerce_sorted_market_data_points_detailed([42], strict=True)


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
