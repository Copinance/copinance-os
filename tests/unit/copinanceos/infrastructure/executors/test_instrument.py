"""Unit tests for instrument analysis executor."""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from copinanceos.application.use_cases.analyze import INSTRUMENT_DETERMINISTIC_TYPE
from copinanceos.application.use_cases.fundamentals import (
    GetStockFundamentalsRequest,
    GetStockFundamentalsResponse,
    GetStockFundamentalsUseCase,
)
from copinanceos.application.use_cases.market import (
    GetHistoricalDataResponse,
    GetHistoricalDataUseCase,
    GetInstrumentResponse,
    GetInstrumentUseCase,
    GetOptionsChainRequest,
    GetOptionsChainResponse,
    GetOptionsChainUseCase,
    GetQuoteRequest,
    GetQuoteResponse,
    GetQuoteUseCase,
)
from copinanceos.domain.models.fundamentals import StockFundamentals
from copinanceos.domain.models.job import Job, JobScope, JobTimeframe
from copinanceos.domain.models.market import (
    MarketDataPoint,
    MarketType,
    OptionContract,
    OptionsChain,
    OptionSide,
)
from copinanceos.domain.models.stock import Stock
from copinanceos.infrastructure.executors import InstrumentAnalysisExecutor


@pytest.mark.unit
class TestInstrumentAnalysisExecutor:
    def test_get_executor_id(self) -> None:
        executor = InstrumentAnalysisExecutor()
        assert executor.get_executor_id() == "instrument_analysis"

    @pytest.mark.asyncio
    async def test_validate_equity_job(self) -> None:
        executor = InstrumentAnalysisExecutor()
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="AAPL",
            timeframe=JobTimeframe.MID_TERM,
            execution_type=INSTRUMENT_DETERMINISTIC_TYPE,
        )
        assert await executor.validate(job) is True

    @pytest.mark.asyncio
    async def test_execute_equity_analysis(self) -> None:
        mock_instrument_use_case = AsyncMock(spec=GetInstrumentUseCase)
        mock_instrument_use_case.execute = AsyncMock(
            return_value=GetInstrumentResponse(
                instrument=Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ")
            )
        )
        mock_quote_use_case = AsyncMock(spec=GetQuoteUseCase)
        mock_quote_use_case.execute = AsyncMock(
            return_value=GetQuoteResponse(
                quote={"symbol": "AAPL", "current_price": "180"},
                symbol="AAPL",
            )
        )
        mock_history_use_case = AsyncMock(spec=GetHistoricalDataUseCase)
        mock_history_use_case.execute = AsyncMock(
            return_value=GetHistoricalDataResponse(
                data=[
                    MarketDataPoint(
                        symbol="AAPL",
                        timestamp=datetime.fromisoformat("2024-01-01T00:00:00"),
                        open_price=Decimal("175"),
                        close_price=Decimal("180"),
                        high_price=Decimal("181"),
                        low_price=Decimal("174"),
                        volume=1000,
                    )
                ],
                symbol="AAPL",
            )
        )
        mock_fundamentals_use_case = AsyncMock(spec=GetStockFundamentalsUseCase)
        mock_fundamentals_use_case.execute = AsyncMock(
            return_value=GetStockFundamentalsResponse(
                fundamentals=StockFundamentals(
                    symbol="AAPL",
                    company_name="Apple Inc.",
                    provider="test",
                    data_as_of=datetime.fromisoformat("2024-01-01T00:00:00"),
                )
            )
        )

        executor = InstrumentAnalysisExecutor(
            get_instrument_use_case=mock_instrument_use_case,
            get_quote_use_case=mock_quote_use_case,
            get_historical_data_use_case=mock_history_use_case,
            fundamentals_use_case=mock_fundamentals_use_case,
        )
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="AAPL",
            timeframe=JobTimeframe.SHORT_TERM,
            execution_type=INSTRUMENT_DETERMINISTIC_TYPE,
        )

        results = await executor.execute(job, {})
        assert results["execution_type"] == "instrument_analysis"
        assert results["instrument_symbol"] == "AAPL"
        assert results["market_type"] == "equity"
        assert "instrument" in results
        fundamentals_request = mock_fundamentals_use_case.execute.call_args[0][0]
        assert isinstance(fundamentals_request, GetStockFundamentalsRequest)

    @pytest.mark.asyncio
    async def test_execute_options_analysis(self) -> None:
        mock_quote_use_case = AsyncMock(spec=GetQuoteUseCase)
        mock_quote_use_case.execute = AsyncMock(
            return_value=GetQuoteResponse(
                quote={"symbol": "AAPL", "current_price": "180"},
                symbol="AAPL",
            )
        )
        mock_options_use_case = AsyncMock(spec=GetOptionsChainUseCase)
        mock_options_use_case.execute = AsyncMock(
            return_value=GetOptionsChainResponse(
                chain=OptionsChain(
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
                ),
                underlying_symbol="AAPL",
            )
        )

        executor = InstrumentAnalysisExecutor(
            get_quote_use_case=mock_quote_use_case,
            get_options_chain_use_case=mock_options_use_case,
        )
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.OPTIONS,
            instrument_symbol="AAPL",
            timeframe=JobTimeframe.SHORT_TERM,
            execution_type=INSTRUMENT_DETERMINISTIC_TYPE,
        )

        results = await executor.execute(job, {"option_side": "call"})
        assert results["execution_type"] == "instrument_analysis"
        assert results["market_type"] == "options"
        assert results["options_chain"]["calls_count"] == 1
        options_request = mock_options_use_case.execute.call_args[0][0]
        assert isinstance(options_request, GetOptionsChainRequest)
        quote_request = mock_quote_use_case.execute.call_args[0][0]
        assert isinstance(quote_request, GetQuoteRequest)
