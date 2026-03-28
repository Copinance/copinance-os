"""StrategySignal contract."""

import pytest

from copinance_os.domain.strategies.signal import StrategySignal


@pytest.mark.unit
def test_strategy_signal_valid() -> None:
    s = StrategySignal(strategy_id="sma_cross", weights=[0.0, 1.0, 1.0])
    assert s.strategy_id == "sma_cross"
    assert len(s.weights) == 3


@pytest.mark.unit
def test_strategy_signal_rejects_nan() -> None:
    with pytest.raises(ValueError, match="finite"):
        StrategySignal(strategy_id="x", weights=[1.0, float("nan")])
