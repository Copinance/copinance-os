"""Momentum oscillators (pure, deterministic)."""

from __future__ import annotations


def relative_strength_index(prices: list[float], period: int = 14) -> float | None:
    """RSI using the same construction as the previous pandas implementation:

    simple averages of gains and losses over the **last** ``period`` price changes.

    Args:
        prices: Closing prices, most recent last.
        period: Lookback for average gain/loss.

    Returns:
        RSI in [0, 100], or ``None`` if insufficient data.
    """
    if len(prices) < period + 1:
        return None

    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    window = changes[-period:]
    gains = [c if c > 0 else 0.0 for c in window]
    losses = [-c if c < 0 else 0.0 for c in window]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))
