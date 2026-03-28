"""Trend-style indicators: moving averages (pure, deterministic)."""

from __future__ import annotations


def simple_moving_average(prices: list[float], window: int) -> list[float | None]:
    """Simple moving average aligned to input length (oldest first).

    Positions ``0 .. window-2`` are ``None`` (insufficient history); from
    ``window-1`` onward values are the mean of the last ``window`` prices.

    Args:
        prices: Closing prices, oldest first.
        window: Lookback window (>=1).

    Returns:
        List of same length as ``prices``.
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    if len(prices) < window:
        return [None] * len(prices)

    n = len(prices)
    out: list[float | None] = []
    for i in range(n):
        if i < window - 1:
            out.append(None)
        else:
            s = sum(prices[i - window + 1 : i + 1])
            out.append(s / window)
    return out
