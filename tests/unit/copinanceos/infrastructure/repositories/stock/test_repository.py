"""Unit tests for the equity instrument repository."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from copinanceos.domain.models.market import MarketDataPoint
from copinanceos.domain.models.stock import Stock
from copinanceos.domain.ports.storage import Storage
from copinanceos.infrastructure.repositories.stock.repository import StockRepositoryImpl


@pytest.mark.unit
class TestStockRepositoryImpl:
    def test_initialization_with_default_storage(self) -> None:
        with patch(
            "copinanceos.infrastructure.repositories.stock.repository.create_storage"
        ) as mock_create_storage:
            mock_storage = MagicMock(spec=Storage)
            mock_storage.get_collection = MagicMock(return_value={})
            mock_create_storage.return_value = mock_storage

            repository = StockRepositoryImpl()

        mock_storage.get_collection.assert_called_once_with("market/instruments/equities", Stock)
        assert repository._market_data == {}

    def test_initialization_with_custom_storage(self) -> None:
        mock_storage = MagicMock(spec=Storage)
        mock_storage.get_collection = MagicMock(return_value={})

        repository = StockRepositoryImpl(storage=mock_storage)

        mock_storage.get_collection.assert_called_once_with("market/instruments/equities", Stock)
        assert repository._market_data == {}

    @pytest.mark.asyncio
    async def test_get_by_symbol_and_search(self) -> None:
        mock_storage = MagicMock(spec=Storage)
        apple = Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ")
        microsoft = Stock(symbol="MSFT", name="Microsoft Corporation", exchange="NASDAQ")
        mock_storage.get_collection = MagicMock(
            return_value={apple.id: apple, microsoft.id: microsoft}
        )

        repository = StockRepositoryImpl(storage=mock_storage)

        assert (await repository.get_by_symbol("aapl")) is apple
        assert (await repository.get_by_symbol("unknown")) is None

        results = await repository.search("Apple")
        assert len(results) == 1
        assert results[0].symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_save_persists_to_new_collection_name(self) -> None:
        mock_storage = MagicMock(spec=Storage)
        collection: dict = {}
        mock_storage.get_collection = MagicMock(return_value=collection)
        mock_storage.save = MagicMock()

        repository = StockRepositoryImpl(storage=mock_storage)
        stock = Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ")

        saved = await repository.save(stock)

        assert saved is stock
        assert collection[stock.id] is stock
        mock_storage.save.assert_called_once_with("market/instruments/equities")

    @pytest.mark.asyncio
    async def test_get_market_data(self) -> None:
        mock_storage = MagicMock(spec=Storage)
        mock_storage.get_collection = MagicMock(return_value={})
        repository = StockRepositoryImpl(storage=mock_storage)

        point = MarketDataPoint(
            symbol="AAPL",
            timestamp=datetime(2024, 1, 1, tzinfo=UTC),
            open_price=Decimal("150"),
            close_price=Decimal("151"),
            high_price=Decimal("152"),
            low_price=Decimal("149"),
            volume=1000000,
        )
        repository._market_data["AAPL"] = [point]

        assert await repository.get_market_data("aapl") == [point]
