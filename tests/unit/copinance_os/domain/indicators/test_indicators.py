"""Unit tests for pure domain indicators."""

import pytest

from copinance_os.domain.indicators import (
    IndicatorResult,
    log_returns_from_prices,
    relative_strength_index,
    rolling_volatility_annualized_from_prices,
    simple_moving_average,
)


@pytest.mark.unit
class TestLogReturns:
    def test_log_returns_length_and_values(self) -> None:
        prices = [100.0, 102.0, 101.0, 105.0]
        lr = log_returns_from_prices(prices)
        assert len(lr) == 3
        assert lr[0] == pytest.approx(0.019802627, rel=1e-5)
        assert lr[1] == pytest.approx(-0.009852296, rel=1e-5)

    def test_empty_and_single(self) -> None:
        assert log_returns_from_prices([]) == []
        assert log_returns_from_prices([100.0]) == []


@pytest.mark.unit
class TestSMA:
    def test_sma_alignment(self) -> None:
        prices = [100.0, 102.0, 101.0, 105.0, 108.0]
        out = simple_moving_average(prices, 3)
        assert len(out) == 5
        assert out[0] is None and out[1] is None
        assert out[2] == pytest.approx((100 + 102 + 101) / 3)


@pytest.mark.unit
class TestRSI:
    def test_rsi_requires_period_plus_one(self) -> None:
        assert relative_strength_index([100.0] * 10, period=14) is None

    def test_rsi_bounded(self) -> None:
        # Monotone up -> high RSI
        prices = [100.0 + i * 0.5 for i in range(30)]
        r = relative_strength_index(prices, period=14)
        assert r is not None
        assert 0 <= r <= 100


@pytest.mark.unit
class TestIndicatorResultModel:
    def test_indicator_result_roundtrip(self) -> None:
        r = IndicatorResult(name="sma_5", values=[None, None, 101.0], parameters={"window": 5})
        assert r.name == "sma_5"
        assert r.values[2] == 101.0


@pytest.mark.unit
class TestRollingVol:
    def test_rolling_vol_alignment(self) -> None:
        prices = [100.0 + i * 0.1 + (i % 3) * 0.5 for i in range(50)]
        vol = rolling_volatility_annualized_from_prices(prices, window=20)
        assert len(vol) == len(prices)
        assert vol[0] is None
        assert all(v is None for v in vol[1:21])
        assert vol[21] is not None
