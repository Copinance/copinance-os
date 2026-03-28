"""Pure helpers for macro time-series summaries (no I/O)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from copinance_os.domain.models.macro import MacroDataPoint


def macro_last_n(points: list[MacroDataPoint], n: int) -> list[MacroDataPoint]:
    """Return the last ``n`` points (or all if fewer than ``n``)."""
    return points[-n:] if len(points) >= n else points


def macro_scalar_to_decimal(val: float | int | str) -> Decimal:
    """Convert a scalar to Decimal (macro tool conventions)."""
    return Decimal(str(val))


def macro_series_metrics(points: list[MacroDataPoint], lookback_points: int = 20) -> dict[str, Any]:
    """Rolling summary for a macro series (latest value and optional change vs lookback)."""
    if not points:
        return {
            "available": False,
            "error": "No data points",
            "data_points": 0,
            "latest": None,
            "change_20d": None,
            "unit": None,
        }

    pts = [p for p in points if p.value is not None]
    if not pts:
        return {
            "available": False,
            "error": "No valid values",
            "data_points": 0,
            "latest": None,
            "change_20d": None,
            "unit": None,
        }

    latest = pts[-1]
    try:
        latest_value = float(latest.value) if latest.value is not None else 0.0
    except (TypeError, ValueError):
        return {
            "available": False,
            "error": f"Invalid data type: {type(latest.value)}",
            "data_points": len(pts),
            "latest": None,
            "change_20d": None,
            "unit": None,
        }

    result: dict[str, Any] = {
        "available": True,
        "error": None,
        "latest": {"timestamp": latest.timestamp.isoformat(), "value": latest_value},
        "data_points": len(pts),
        "change_20d": None,
        "unit": None,
    }

    if len(pts) > lookback_points:
        prev = pts[-(lookback_points + 1)]
        delta = latest.value - prev.value
        result["change_20d"] = float(delta)

    return result
