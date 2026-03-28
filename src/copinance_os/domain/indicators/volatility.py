"""Realized and EWMA volatility from prices (pure numpy; no I/O)."""

from __future__ import annotations

from typing import cast

import numpy as np

from copinance_os.domain.indicators.returns import log_returns_from_prices


def rolling_volatility_annualized_from_prices(
    prices: list[float],
    window: int = 20,
    trading_days_per_year: int = 252,
) -> list[float | None]:
    """Rolling sample volatility of log-returns, annualized (matches prior pandas path).

    Alignment: index ``0`` and ``1..window`` are ``None``; first valid at price index
    ``window + 1`` (same as ``[None] + [None] * window + rolling[window:]`` on returns).
    """
    if len(prices) < window + 1:
        return [None] * len(prices)

    log_returns_list = log_returns_from_prices(prices)
    if len(log_returns_list) < window:
        return [None] * len(prices)

    arr = np.asarray(log_returns_list, dtype=float)
    n = len(arr)
    ann = float(trading_days_per_year) ** 0.5
    rolling_std: list[float | None] = []
    for i in range(n):
        if i < window - 1:
            rolling_std.append(None)
        else:
            chunk = arr[i - window + 1 : i + 1]
            std = float(np.std(chunk, ddof=1))
            rolling_std.append(std * ann)

    valid_vols = rolling_std[window:]
    result = cast(
        list[float | None],
        [None] + [None] * window + list(valid_vols),
    )
    if len(result) > len(prices):
        result = result[: len(prices)]
    elif len(result) < len(prices):
        result.extend([None] * (len(prices) - len(result)))
    return result


def ewma_volatility_annualized_from_prices(
    prices: list[float],
    lambda_param: float = 0.94,
    trading_days_per_year: int = 252,
) -> list[float | None]:
    """RiskMetrics-style EWMA volatility of log-returns, annualized.

    Returns length ``len(prices) - 1``: leading ``None`` for the first price, then
    one vol per subsequent price (from EWMA variance on log-returns).
    """
    if len(prices) < 2:
        return [None] * len(prices)

    log_returns = log_returns_from_prices(prices)
    if not log_returns:
        return [None] * len(prices)

    ewma_variance = log_returns[0] ** 2
    ewma_vols: list[float | None] = [None]
    ann = float(trading_days_per_year) ** 0.5

    for i in range(1, len(log_returns)):
        ewma_variance = lambda_param * ewma_variance + (1.0 - lambda_param) * (log_returns[i] ** 2)
        ewma_vols.append((ewma_variance**0.5) * ann)

    return ewma_vols
