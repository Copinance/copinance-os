"""Simple long-only backtest."""

import pytest

from copinance_os.domain.backtest import (
    SimpleBacktestConfig,
    run_simple_long_only_backtest,
)


@pytest.mark.unit
def test_flat_market_zero_weight() -> None:
    closes = [100.0, 100.0, 100.0]
    weights = [0.0, 0.0, 0.0]
    cfg = SimpleBacktestConfig(initial_cash=10_000.0)
    out = run_simple_long_only_backtest(closes, weights, cfg)
    assert out.equity_curve[-1] == pytest.approx(10_000.0)
    assert out.total_return == pytest.approx(0.0)


@pytest.mark.unit
def test_bull_full_invested() -> None:
    closes = [100.0, 110.0, 121.0]
    weights = [1.0, 1.0, 1.0]
    cfg = SimpleBacktestConfig(initial_cash=1.0, commission_bps=0, slippage_bps=0)
    out = run_simple_long_only_backtest(closes, weights, cfg)
    assert out.total_return == pytest.approx(0.21)
    assert out.equity_curve[-1] == pytest.approx(1.0 * 1.1 * 1.1)


@pytest.mark.unit
def test_commission_reduces_equity() -> None:
    closes = [100.0, 100.0, 100.0]
    weights = [0.0, 1.0, 1.0]
    cfg = SimpleBacktestConfig(initial_cash=10_000.0, commission_bps=100.0, slippage_bps=0)
    out = run_simple_long_only_backtest(closes, weights, cfg)
    # Turnover when moving 0 → 100% long is charged on the step where the new weight applies.
    assert out.equity_curve[2] < 10_000.0


@pytest.mark.unit
def test_invalid_weight_raises() -> None:
    with pytest.raises(ValueError, match="0, 1"):
        run_simple_long_only_backtest(
            [1.0, 2.0],
            [1.5, 1.0],
            SimpleBacktestConfig(initial_cash=1.0),
        )
