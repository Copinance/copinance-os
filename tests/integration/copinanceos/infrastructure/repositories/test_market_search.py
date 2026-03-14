"""Integration tests for market instrument search functionality."""

import pytest

from copinanceos.application.use_cases.market import (
    SearchInstrumentsRequest,
    SearchInstrumentsUseCase,
)
from copinanceos.domain.models.stock import Stock
from copinanceos.domain.ports.repositories import StockRepository


@pytest.mark.integration
class TestMarketSearchIntegration:
    @pytest.fixture
    def use_case(self, stock_repository: StockRepository) -> SearchInstrumentsUseCase:
        return SearchInstrumentsUseCase(stock_repository)

    @pytest.mark.asyncio
    async def test_search_by_symbol_exact_match(
        self, stock_repository: StockRepository, use_case: SearchInstrumentsUseCase
    ) -> None:
        await stock_repository.save(Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ"))

        response = await use_case.execute(SearchInstrumentsRequest(query="AAPL", limit=10))

        assert len(response.instruments) == 1
        assert response.instruments[0].symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_search_by_name_partial_match(
        self, stock_repository: StockRepository, use_case: SearchInstrumentsUseCase
    ) -> None:
        await stock_repository.save(Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ"))
        await stock_repository.save(
            Stock(symbol="MSFT", name="Microsoft Corporation", exchange="NASDAQ")
        )

        response = await use_case.execute(SearchInstrumentsRequest(query="Apple", limit=10))

        assert len(response.instruments) == 1
        assert response.instruments[0].symbol == "AAPL"
