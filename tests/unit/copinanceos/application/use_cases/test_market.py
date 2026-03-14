"""Unit tests for market instrument use cases."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copinanceos.application.use_cases.market import (
    GetInstrumentRequest,
    GetInstrumentUseCase,
    GetMarketDataRequest,
    GetMarketDataUseCase,
    InstrumentSearchMode,
    SearchInstrumentsRequest,
    SearchInstrumentsUseCase,
)
from copinanceos.domain.models.market import MarketDataPoint
from copinanceos.domain.models.stock import Stock
from copinanceos.domain.ports.data_providers import MarketDataProvider
from copinanceos.domain.ports.repositories import StockRepository


@pytest.mark.unit
class TestGetInstrumentUseCase:
    def test_initialization(self) -> None:
        mock_repository = MagicMock(spec=StockRepository)
        use_case = GetInstrumentUseCase(instrument_repository=mock_repository)
        assert use_case._instrument_repository is mock_repository

    @pytest.mark.asyncio
    async def test_execute(self) -> None:
        mock_repository = AsyncMock(spec=StockRepository)
        instrument = Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ")
        mock_repository.get_by_symbol = AsyncMock(return_value=instrument)

        use_case = GetInstrumentUseCase(instrument_repository=mock_repository)
        response = await use_case.execute(GetInstrumentRequest(symbol="AAPL"))

        assert response.instrument is not None
        assert response.instrument.symbol == "AAPL"


@pytest.mark.unit
class TestSearchInstrumentsUseCase:
    @pytest.mark.asyncio
    async def test_execute_uses_repository_results(self) -> None:
        mock_repository = AsyncMock(spec=StockRepository)
        mock_repository.search = AsyncMock(
            return_value=[Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ")]
        )
        use_case = SearchInstrumentsUseCase(instrument_repository=mock_repository)

        response = await use_case.execute(SearchInstrumentsRequest(query="Apple", limit=10))

        assert len(response.instruments) == 1
        assert response.instruments[0].symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_execute_general_search_uses_provider(self) -> None:
        mock_repository = AsyncMock(spec=StockRepository)
        mock_repository.search = AsyncMock(return_value=[])
        mock_provider = AsyncMock(spec=MarketDataProvider)
        mock_provider.search_instruments = AsyncMock(
            return_value=[{"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ"}]
        )
        use_case = SearchInstrumentsUseCase(
            instrument_repository=mock_repository,
            market_data_provider=mock_provider,
        )

        with patch.object(use_case, "_fetch_instrument_from_provider") as mock_fetch:
            mock_fetch.return_value = Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ")
            response = await use_case.execute(
                SearchInstrumentsRequest(
                    query="apple",
                    limit=10,
                    search_mode=InstrumentSearchMode.GENERAL,
                )
            )

        assert len(response.instruments) == 1
        mock_provider.search_instruments.assert_called_once_with("apple", limit=10)


@pytest.mark.unit
class TestGetMarketDataUseCase:
    @pytest.mark.asyncio
    async def test_execute(self) -> None:
        mock_repository = AsyncMock(spec=StockRepository)
        data = [
            MarketDataPoint(
                symbol="AAPL",
                timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                open_price=Decimal("150"),
                close_price=Decimal("151"),
                high_price=Decimal("152"),
                low_price=Decimal("149"),
                volume=1000000,
            )
        ]
        mock_repository.get_market_data = AsyncMock(return_value=data)

        use_case = GetMarketDataUseCase(instrument_repository=mock_repository)
        response = await use_case.execute(GetMarketDataRequest(symbol="AAPL", limit=100))

        assert len(response.data) == 1
        assert response.data[0].symbol == "AAPL"
