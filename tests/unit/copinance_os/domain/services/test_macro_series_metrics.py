"""Tests for pure macro series metrics helpers."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from copinance_os.domain.models.macro import MacroDataPoint
from copinance_os.domain.services.macro_series_metrics import (
    macro_last_n,
    macro_scalar_to_decimal,
    macro_series_metrics,
)


@pytest.mark.unit
def test_macro_series_metrics_latest_and_change() -> None:
    base = datetime(2024, 1, 1, tzinfo=UTC)
    pts = [
        MacroDataPoint(
            series_id="T",
            timestamp=base + timedelta(days=i),
            value=Decimal(str(100 + i)),
        )
        for i in range(25)
    ]
    m = macro_series_metrics(pts, lookback_points=20)
    assert m["available"] is True
    assert m["latest"]["value"] == 124.0
    assert m["change_20d"] is not None


@pytest.mark.unit
def test_macro_last_n() -> None:
    base = datetime(2024, 1, 1, tzinfo=UTC)
    pts = [
        MacroDataPoint(series_id="T", timestamp=base, value=Decimal("1")),
        MacroDataPoint(series_id="T", timestamp=base + timedelta(days=1), value=Decimal("2")),
    ]
    assert len(macro_last_n(pts, 1)) == 1


@pytest.mark.unit
def test_macro_scalar_to_decimal() -> None:
    assert macro_scalar_to_decimal(1.5) == Decimal("1.5")
