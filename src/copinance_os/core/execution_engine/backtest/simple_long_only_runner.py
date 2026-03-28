"""Execution layer: run deterministic long-only backtests with observability.

Domain math lives in ``copinance_os.domain.backtest``; this module adds logging and a
stable entrypoint for pipelines and HTTP adapters (no business rules beyond dispatch).
"""

from __future__ import annotations

from collections.abc import Sequence

import structlog

from copinance_os.domain.backtest import (
    SimpleBacktestConfig,
    SimpleBacktestResult,
    run_simple_long_only_backtest,
)

logger = structlog.get_logger(__name__)


def execute_simple_long_only_backtest(
    closes: Sequence[float],
    weights: Sequence[float],
    config: SimpleBacktestConfig,
) -> SimpleBacktestResult:
    """Execute a long-only backtest (delegates to domain; logs steps, re-raises validation)."""
    n = len(closes)
    logger.info(
        "backtest_simple_long_only_start",
        bars=n,
        commission_bps=config.commission_bps,
        slippage_bps=config.slippage_bps,
        initial_cash=config.initial_cash,
    )
    try:
        result = run_simple_long_only_backtest(closes, weights, config)
    except ValueError as e:
        logger.warning("backtest_simple_long_only_validation_failed", error=str(e))
        raise
    logger.info(
        "backtest_simple_long_only_complete",
        total_return=result.total_return,
        max_drawdown=result.max_drawdown,
        sharpe_ratio=result.sharpe_ratio,
    )
    return result
