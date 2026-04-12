"""Instrument executor: options positioning payload on single-expiry deterministic runs."""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from copinance_os.core.execution_engine import InstrumentAnalysisExecutor
from copinance_os.domain.models.job import Job, JobScope, JobTimeframe
from copinance_os.domain.models.market import (
    MarketType,
    OptionContract,
    OptionsChain,
    OptionSide,
)
from copinance_os.research.workflows.analyze import INSTRUMENT_DETERMINISTIC_TYPE
from copinance_os.research.workflows.market import (
    GetOptionsChainRequest,
    GetOptionsChainResponse,
    GetOptionsChainUseCase,
    GetQuoteRequest,
    GetQuoteResponse,
    GetQuoteUseCase,
)


@pytest.mark.unit
async def test_options_single_expiration_includes_positioning_snake_case() -> None:
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

    results = await executor.execute(job, {"option_side": "call", "positioning_window": "near"})
    assert results["execution_type"] == "instrument_analysis"
    pos = results.get("positioning")
    assert isinstance(pos, dict)
    assert pos["symbol"] == "AAPL"
    assert "market_bias" in pos
    assert "iv_metrics" in pos
    assert isinstance(pos["iv_metrics"], dict)
    quote_request = mock_quote_use_case.execute.call_args[0][0]
    assert isinstance(quote_request, GetQuoteRequest)
    options_request = mock_options_use_case.execute.call_args[0][0]
    assert isinstance(options_request, GetOptionsChainRequest)
