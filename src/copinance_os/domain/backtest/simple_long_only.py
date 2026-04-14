"""Long-only backtest: signal at bar t-1 earns bar t return (no lookahead in weights)."""

from __future__ import annotations

import math
from collections.abc import Sequence

from copinance_os.domain.backtest.models import SimpleBacktestConfig, SimpleBacktestResult
from copinance_os.domain.models.methodology import MethodologySpec, analysis_methodology_single_spec


def run_simple_long_only_backtest(
    closes: Sequence[float],
    weights: Sequence[float],
    config: SimpleBacktestConfig,
) -> SimpleBacktestResult:
    """Backtest a long-only strategy with explicit costs.

    **Timing (no lookahead):** ``weights[t]`` is the allocation decided at the close of
    bar ``t`` (after observing ``closes[t]``). It earns the *next* simple return
    ``closes[t+1]/closes[t]-1``. The first weight ``weights[0]`` earns the return from
    bar 0 to 1. The last weight does not earn a subsequent return (series length matches
    ``closes``).

    **Costs:** On each rebalance, turnover ``|w[t] - w[t-1]|`` (with ``w[-1]=0``) pays
    ``(commission_bps + slippage_bps) / 10000`` times pre-cost portfolio value.

    Args:
        closes: Close prices, oldest first, length >= 2.
        weights: Target weights in ``[0, 1]``, same length as ``closes``.
        config: Cash and friction parameters.

    Returns:
        ``SimpleBacktestResult`` with equity path and summary statistics.
    """
    if len(closes) < 2:
        raise ValueError("closes must contain at least two observations")
    if len(weights) != len(closes):
        raise ValueError("weights must align with closes")
    for i, w in enumerate(weights):
        if w < 0 or w > 1:
            raise ValueError(f"weight at {i} must be in [0, 1], got {w}")
        if math.isnan(w) or math.isinf(w):
            raise ValueError("weights must be finite")
    for i, p in enumerate(closes):
        if p <= 0 or math.isnan(p) or math.isinf(p):
            raise ValueError(f"closes must be positive and finite (index {i})")

    fee_rate = (config.commission_bps + config.slippage_bps) / 10000.0
    n = len(closes)
    equity: list[float] = [0.0] * n
    period_ret: list[float | None] = [None] + [0.0] * (n - 1)
    equity[0] = config.initial_cash
    w_prev = 0.0

    for t in range(1, n):
        r_asset = closes[t] / closes[t - 1] - 1.0
        w = weights[t - 1]
        turnover = abs(w - w_prev)
        gross = equity[t - 1] * (1.0 + w * r_asset)
        cost = turnover * equity[t - 1] * fee_rate
        equity[t] = max(gross - cost, 1e-12)
        period_ret[t] = equity[t] / equity[t - 1] - 1.0 if equity[t - 1] > 0 else 0.0
        w_prev = w

    total_return = equity[-1] / equity[0] - 1.0
    peak = equity[0]
    max_dd = 0.0
    for x in equity:
        peak = max(peak, x)
        if peak > 0:
            max_dd = max(max_dd, 1.0 - x / peak)

    rets = [r for r in period_ret[1:] if r is not None]
    sharpe: float | None = None
    if len(rets) > 2:
        mean_r = sum(rets) / len(rets)
        var = sum((x - mean_r) ** 2 for x in rets) / (len(rets) - 1)
        std = math.sqrt(var) if var > 0 else 0.0
        if std > 0:
            sharpe = (mean_r / std) * math.sqrt(float(config.trading_days_per_year))

    spec = MethodologySpec(
        id="backtest.simple_long_only",
        version="v1",
        model_family="long_only_next_bar_return",
        assumptions=(
            "Weights are taken as given (caller must enforce no lookahead).",
            "Fractional shares, no borrow, no dividends; friction is proportional to turnover.",
        ),
        limitations=(
            "Does not model path-dependent orders, market impact beyond slippage bps, or survivorship.",
        ),
        references=(),
        parameters={
            "commission_bps": str(config.commission_bps),
            "slippage_bps": str(config.slippage_bps),
            "trading_days_per_year": str(config.trading_days_per_year),
        },
    )
    methodology = analysis_methodology_single_spec(
        spec=spec,
        data_inputs={"bars": str(n)},
    )

    return SimpleBacktestResult(
        equity_curve=equity,
        period_returns=period_ret,
        total_return=total_return,
        max_drawdown=max_dd,
        sharpe_ratio=sharpe,
        methodology=methodology,
        key_metrics={
            "bars": n,
            "commission_bps": config.commission_bps,
            "slippage_bps": config.slippage_bps,
        },
    )
