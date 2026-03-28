"""Unit tests for market use cases."""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copinance_os.domain.models.market import MarketDataPoint, OptionsChain
from copinance_os.domain.models.stock import Stock
from copinance_os.domain.ports.data_providers import MarketDataProvider
from copinance_os.domain.ports.repositories import StockRepository
from copinance_os.research.workflows.market import (
    GetHistoricalDataRequest,
    GetHistoricalDataUseCase,
    GetInstrumentRequest,
    GetInstrumentUseCase,
    GetOptionsChainRequest,
    GetOptionsChainUseCase,
    GetQuoteRequest,
    GetQuoteUseCase,
    InstrumentSearchMode,
    SearchInstrumentsRequest,
    SearchInstrumentsUseCase,
)


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

        with patch.object(use_case, "_resolve_instrument_from_provider") as mock_resolve:
            mock_resolve.return_value = Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ")
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
class TestGetQuoteUseCase:
    def test_initialization(self) -> None:
        mock_provider = MagicMock(spec=MarketDataProvider)
        use_case = GetQuoteUseCase(market_data_provider=mock_provider)
        assert use_case._market_data_provider is mock_provider

    @pytest.mark.asyncio
    async def test_execute_returns_quote(self) -> None:
        mock_provider = AsyncMock(spec=MarketDataProvider)
        mock_provider.get_quote = AsyncMock(
            return_value={
                "symbol": "AAPL",
                "current_price": Decimal("175.50"),
                "volume": 50_000_000,
            }
        )
        use_case = GetQuoteUseCase(market_data_provider=mock_provider)
        response = await use_case.execute(GetQuoteRequest(symbol="AAPL"))

        assert response.symbol == "AAPL"
        assert response.quote["symbol"] == "AAPL"
        assert response.quote["current_price"] == Decimal("175.50")
        mock_provider.get_quote.assert_called_once_with("AAPL")


@pytest.mark.unit
class TestGetHistoricalDataUseCase:
    @pytest.mark.asyncio
    async def test_execute_returns_data(self) -> None:
        mock_provider = AsyncMock(spec=MarketDataProvider)
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
        mock_provider.get_historical_data = AsyncMock(return_value=data)
        use_case = GetHistoricalDataUseCase(market_data_provider=mock_provider)
        response = await use_case.execute(
            GetHistoricalDataRequest(
                symbol="AAPL",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 31),
                interval="1d",
            )
        )

        assert response.symbol == "AAPL"
        assert len(response.data) == 1
        assert response.data[0].symbol == "AAPL"
        assert response.data[0].close_price == Decimal("151")


@pytest.mark.unit
class TestGetOptionsChainUseCase:
    @pytest.mark.asyncio
    async def test_execute_returns_chain(self) -> None:
        mock_provider = AsyncMock(spec=MarketDataProvider)
        chain = OptionsChain(
            underlying_symbol="AAPL",
            expiration_date=date(2025, 1, 17),
            underlying_price=Decimal("175.00"),
            calls=[],
            puts=[],
        )
        mock_provider.get_options_chain = AsyncMock(return_value=chain)
        use_case = GetOptionsChainUseCase(market_data_provider=mock_provider)
        response = await use_case.execute(
            GetOptionsChainRequest(underlying_symbol="AAPL", expiration_date=None)
        )

        assert response.underlying_symbol == "AAPL"
        assert response.chain.underlying_symbol == "AAPL"
        assert response.chain.underlying_price == Decimal("175.00")
        mock_provider.get_options_chain.assert_called_once_with(
            underlying_symbol="AAPL",
            expiration_date=None,
        )
