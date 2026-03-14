"""Unit tests for market instrument workflow executor."""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from copinanceos.application.use_cases.fundamentals import (
    ResearchStockFundamentalsResponse,
    ResearchStockFundamentalsUseCase,
)
from copinanceos.application.use_cases.market import GetInstrumentResponse, GetInstrumentUseCase
from copinanceos.domain.models.fundamentals import StockFundamentals
from copinanceos.domain.models.job import Job, JobScope, JobTimeframe
from copinanceos.domain.models.market import MarketType, OptionContract, OptionsChain, OptionSide
from copinanceos.domain.models.stock import Stock
from copinanceos.domain.ports.data_providers import MarketDataProvider
from copinanceos.infrastructure.workflows import MarketInstrumentWorkflowExecutor


@pytest.mark.unit
class TestMarketInstrumentWorkflowExecutor:
    def test_get_workflow_type(self) -> None:
        executor = MarketInstrumentWorkflowExecutor()
        assert executor.get_workflow_type() == "instrument"

    @pytest.mark.asyncio
    async def test_validate_equity_job(self) -> None:
        executor = MarketInstrumentWorkflowExecutor()
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="AAPL",
            timeframe=JobTimeframe.MID_TERM,
            workflow_type="equity",
        )
        assert await executor.validate(job) is True

    @pytest.mark.asyncio
    async def test_execute_equity_workflow(self) -> None:
        mock_instrument_use_case = AsyncMock(spec=GetInstrumentUseCase)
        mock_instrument_use_case.execute = AsyncMock(
            return_value=GetInstrumentResponse(
                instrument=Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ")
            )
        )
        mock_market_provider = AsyncMock(spec=MarketDataProvider)
        mock_market_provider.get_quote = AsyncMock(
            return_value={"symbol": "AAPL", "current_price": "180"}
        )
        mock_market_provider.get_historical_data = AsyncMock(return_value=[])
        mock_fundamentals_use_case = AsyncMock(spec=ResearchStockFundamentalsUseCase)
        mock_fundamentals_use_case.execute = AsyncMock(
            return_value=ResearchStockFundamentalsResponse(
                fundamentals=StockFundamentals(
                    symbol="AAPL",
                    company_name="Apple Inc.",
                    provider="test",
                    data_as_of=datetime.fromisoformat("2024-01-01T00:00:00"),
                )
            )
        )

        executor = MarketInstrumentWorkflowExecutor(
            get_instrument_use_case=mock_instrument_use_case,
            market_data_provider=mock_market_provider,
            fundamentals_use_case=mock_fundamentals_use_case,
        )
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="AAPL",
            timeframe=JobTimeframe.SHORT_TERM,
            workflow_type="equity",
        )

        results = await executor.execute(job, {})
        assert results["workflow_type"] == "equity"
        assert results["instrument_symbol"] == "AAPL"
        assert results["market_type"] == "equity"
        assert "instrument" in results

    @pytest.mark.asyncio
    async def test_execute_options_workflow(self) -> None:
        mock_market_provider = AsyncMock(spec=MarketDataProvider)
        mock_market_provider.get_quote = AsyncMock(
            return_value={"symbol": "AAPL", "current_price": "180"}
        )
        mock_market_provider.get_options_chain = AsyncMock(
            return_value=OptionsChain(
                underlying_symbol="AAPL",
                expiration_date=date(2026, 6, 19),
                available_expirations=[date(2026, 6, 19)],
                underlying_price=Decimal("180"),
                calls=[
                    OptionContract(
                        underlying_symbol="AAPL",
                        contract_symbol="AAPL260619C00180000",
                        side=OptionSide.CALL,
                        strike=Decimal("180"),
                        expiration_date=date(2026, 6, 19),
                        last_price=Decimal("12"),
                        open_interest=100,
                        volume=50,
                        implied_volatility=Decimal("0.25"),
                    )
                ],
                puts=[],
            )
        )

        executor = MarketInstrumentWorkflowExecutor(market_data_provider=mock_market_provider)
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.OPTIONS,
            instrument_symbol="AAPL",
            timeframe=JobTimeframe.SHORT_TERM,
            workflow_type="options",
        )

        results = await executor.execute(job, {"option_side": "call"})
        assert results["workflow_type"] == "options"
        assert results["market_type"] == "options"
        assert results["options_chain"]["calls_count"] == 1
