"""IV percentile rank utility for options positioning consumers."""

from __future__ import annotations

from collections.abc import Sequence


def iv_percentile_rank(current_iv: float, history: Sequence[float]) -> int:
    """Return the percentile rank of *current_iv* within *history* as an integer [0, 100].

    Rank is computed as the fraction of historical values strictly below *current_iv*,
    multiplied by 100 and rounded.  This is the standard IV-rank convention used by
    options desks: a rank of 0 means current IV is at or below all prior observations;
    100 means it exceeds every prior observation.

    Edge cases:
    - Empty or single-item *history*: returns 50 (neutral / no context).
    - *current_iv* ≤ 0: returns 0 (degenerate input).

    Library consumers supply their own rolling history (e.g. 252 trading days of
    at-the-money IV snapshots per symbol).  Copinance-OS does not persist IV history
    internally — that is the consuming backend's responsibility.

    Args:
        current_iv: Current implied volatility value (same units as *history*).
        history: Sequence of historical IV values, any order, any length.

    Returns:
        Integer 0–100 representing the percentile rank.
    """
    if current_iv <= 0:
        return 0
    if len(history) <= 1:
        return 50
    below = sum(1 for h in history if h < current_iv)
    return round(below / len(history) * 100)
