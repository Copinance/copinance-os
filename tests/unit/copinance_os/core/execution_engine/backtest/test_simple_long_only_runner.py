"""Execution-layer backtest delegates to domain with same numerics."""

import pytest

from copinance_os.core.execution_engine.backtest import execute_simple_long_only_backtest
from copinance_os.domain.backtest import SimpleBacktestConfig, run_simple_long_only_backtest


@pytest.mark.unit
def test_execute_matches_domain() -> None:
    closes = [100.0, 110.0, 121.0]
    weights = [1.0, 1.0, 1.0]
    cfg = SimpleBacktestConfig(initial_cash=1.0)
    a = execute_simple_long_only_backtest(closes, weights, cfg)
    b = run_simple_long_only_backtest(closes, weights, cfg)
    da = a.model_dump(mode="json")
    db = b.model_dump(mode="json")
    da["methodology"].pop("computed_at", None)
    db["methodology"].pop("computed_at", None)
    assert da == db


@pytest.mark.unit
def test_execute_propagates_validation() -> None:
    with pytest.raises(ValueError, match="align"):
        execute_simple_long_only_backtest(
            [1.0, 2.0],
            [1.0],
            SimpleBacktestConfig(initial_cash=1.0),
        )
