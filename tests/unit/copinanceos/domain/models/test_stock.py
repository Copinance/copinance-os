"""Unit tests for equity and market domain models."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from copinanceos.domain.models.market import MarketDataPoint
from copinanceos.domain.models.stock import Stock


@pytest.mark.unit
class TestStockModel:
    def test_create_stock(self) -> None:
        stock = Stock(
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
            sector="Technology",
        )

        assert stock.symbol == "AAPL"
        assert stock.name == "Apple Inc."
        assert stock.exchange == "NASDAQ"
        assert stock.sector == "Technology"

    def test_market_data_point_value_object(self) -> None:
        data = MarketDataPoint(
            symbol="AAPL",
            timestamp=datetime.now(UTC),
            open_price=Decimal("150.00"),
            close_price=Decimal("151.00"),
            high_price=Decimal("152.00"),
            low_price=Decimal("149.00"),
            volume=1000000,
        )

        assert data.symbol == "AAPL"
        assert data.volume == 1000000
