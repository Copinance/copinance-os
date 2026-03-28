"""Log-returns and related transforms (pure, deterministic)."""

from __future__ import annotations

from collections.abc import Sequence
from math import log


def log_returns_from_prices(prices: Sequence[float]) -> list[float]:
    """Compute log-returns r_t = ln(P_t) - ln(P_{t-1}) for consecutive closes.

    Non-positive prices use ln(0) := 0.0 for the log level (legacy compatibility
    with prior pandas-based behavior).

    Returns:
        List of length ``len(prices) - 1`` (empty if fewer than two prices).
    """
    if len(prices) < 2:
        return []

    out: list[float] = []
    for i in range(1, len(prices)):
        p0 = prices[i - 1]
        p1 = prices[i]
        lp0 = log(p0) if p0 > 0 else 0.0
        lp1 = log(p1) if p1 > 0 else 0.0
        out.append(lp1 - lp0)
    return out
