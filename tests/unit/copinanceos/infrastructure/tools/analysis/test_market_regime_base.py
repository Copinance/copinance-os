"""Unit tests for market regime detection base functions."""

import pytest

from copinanceos.infrastructure.tools.analysis.market_regime.base import (
    _calculate_log_returns,
    _calculate_moving_average,
)


@pytest.mark.unit
class TestBaseHelperFunctions:
    """Test base helper functions for market regime detection."""

    def test_calculate_moving_average_sufficient_data(self) -> None:
        """Test moving average calculation with sufficient data."""
        prices = [100.0, 102.0, 101.0, 105.0, 108.0, 107.0, 110.0, 112.0, 115.0, 118.0]
        window = 3

        result = _calculate_moving_average(prices, window)

        assert len(result) == len(prices)
        assert result[0] is None  # First window-1 values are None
        assert result[1] is None
        assert result[2] is not None  # First valid MA
        assert result[2] == (100.0 + 102.0 + 101.0) / 3
        assert result[-1] is not None  # Last value should be valid

    def test_calculate_moving_average_insufficient_data(self) -> None:
        """Test moving average with insufficient data."""
        prices = [100.0, 102.0]
        window = 5

        result = _calculate_moving_average(prices, window)

        assert len(result) == len(prices)
        assert all(v is None for v in result)

    def test_calculate_log_returns(self) -> None:
        """Test log-returns calculation."""
        prices = [100.0, 102.0, 101.0, 105.0]

        log_returns = _calculate_log_returns(prices)

        assert len(log_returns) == len(prices) - 1
        assert log_returns[0] == pytest.approx(0.0198, abs=0.0001)  # ln(102/100)
        assert log_returns[1] == pytest.approx(-0.0099, abs=0.0001)  # ln(101/102)

    def test_calculate_log_returns_insufficient_data(self) -> None:
        """Test log-returns with insufficient data."""
        prices = [100.0]

        log_returns = _calculate_log_returns(prices)

        assert len(log_returns) == 0

    def test_calculate_log_returns_empty(self) -> None:
        """Test log-returns with empty list."""
        prices: list[float] = []

        log_returns = _calculate_log_returns(prices)

        assert len(log_returns) == 0
