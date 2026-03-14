"""Unit tests for progressive analyze use cases and default runners."""

from unittest.mock import AsyncMock

import pytest

from copinanceos.application.runners import (
    DefaultAnalyzeInstrumentRunner,
    DefaultAnalyzeMarketRunner,
)
from copinanceos.application.use_cases.analyze import (
    INSTRUMENT_DETERMINISTIC_TYPE,
    INSTRUMENT_QUESTION_DRIVEN_TYPE,
    MARKET_DETERMINISTIC_TYPE,
    MARKET_QUESTION_DRIVEN_TYPE,
    AnalyzeInstrumentRequest,
    AnalyzeInstrumentRunner,
    AnalyzeInstrumentUseCase,
    AnalyzeMarketRequest,
    AnalyzeMarketRunner,
    AnalyzeMarketUseCase,
    AnalyzeMode,
)
from copinanceos.domain.models.job import JobScope, JobTimeframe, RunJobResult
from copinanceos.domain.models.market import MarketType, OptionSide
from copinanceos.domain.ports.analysis_execution import JobRunner


@pytest.mark.unit
class TestAnalyzeInstrumentUseCase:
    @pytest.mark.asyncio
    async def test_execute_delegates_to_runner(self) -> None:
        mock_runner = AsyncMock(spec=AnalyzeInstrumentRunner)
        mock_runner.run = AsyncMock(
            return_value=RunJobResult(success=True, results={"summary": "ok"}, error_message=None)
        )
        use_case = AnalyzeInstrumentUseCase(analyze_instrument_runner=mock_runner)
        request = AnalyzeInstrumentRequest(symbol="AAPL")

        response = await use_case.execute(request)

        assert response.success is True
        mock_runner.run.assert_called_once_with(request)


@pytest.mark.unit
class TestDefaultAnalyzeInstrumentRunner:
    @pytest.mark.asyncio
    async def test_run_builds_static_equity_job(self) -> None:
        mock_job_runner = AsyncMock(spec=JobRunner)
        mock_job_runner.run = AsyncMock(
            return_value=RunJobResult(success=True, results={"summary": "ok"}, error_message=None)
        )
        runner = DefaultAnalyzeInstrumentRunner(job_runner=mock_job_runner)

        await runner.run(AnalyzeInstrumentRequest(symbol="AAPL"))

        job = mock_job_runner.run.call_args[0][0]
        context = mock_job_runner.run.call_args[0][1]
        assert job.scope == JobScope.INSTRUMENT
        assert job.market_type == MarketType.EQUITY
        assert job.instrument_symbol == "AAPL"
        assert job.execution_type == INSTRUMENT_DETERMINISTIC_TYPE
        assert job.timeframe == JobTimeframe.MID_TERM
        assert context["question"] is None

    @pytest.mark.asyncio
    async def test_run_builds_agentic_options_job(self) -> None:
        mock_job_runner = AsyncMock(spec=JobRunner)
        mock_job_runner.run = AsyncMock(
            return_value=RunJobResult(success=True, results={}, error_message=None)
        )
        runner = DefaultAnalyzeInstrumentRunner(job_runner=mock_job_runner)

        await runner.run(
            AnalyzeInstrumentRequest(
                symbol="AAPL",
                market_type=MarketType.OPTIONS,
                question="Is skew bearish?",
                mode=AnalyzeMode.AUTO,
                expiration_date="2026-06-19",
                option_side=OptionSide.CALL,
            )
        )

        job = mock_job_runner.run.call_args[0][0]
        context = mock_job_runner.run.call_args[0][1]
        assert job.scope == JobScope.INSTRUMENT
        assert job.market_type == MarketType.OPTIONS
        assert job.instrument_symbol == "AAPL"
        assert job.execution_type == INSTRUMENT_QUESTION_DRIVEN_TYPE
        assert job.timeframe == JobTimeframe.SHORT_TERM
        assert context["question"] == "Is skew bearish?"
        assert context["expiration_date"] == "2026-06-19"
        assert context["option_side"] == "call"


@pytest.mark.unit
class TestAnalyzeMarketUseCase:
    @pytest.mark.asyncio
    async def test_execute_delegates_to_runner(self) -> None:
        mock_runner = AsyncMock(spec=AnalyzeMarketRunner)
        mock_runner.run = AsyncMock(
            return_value=RunJobResult(success=True, results={"macro": {}}, error_message=None)
        )
        use_case = AnalyzeMarketUseCase(analyze_market_runner=mock_runner)
        request = AnalyzeMarketRequest(market_index="QQQ", lookback_days=90, include_vix=False)

        response = await use_case.execute(request)

        assert response.success is True
        mock_runner.run.assert_called_once_with(request)


@pytest.mark.unit
class TestDefaultAnalyzeMarketRunner:
    @pytest.mark.asyncio
    async def test_run_builds_deterministic_market_job(self) -> None:
        mock_job_runner = AsyncMock(spec=JobRunner)
        mock_job_runner.run = AsyncMock(
            return_value=RunJobResult(success=True, results={"macro": {}}, error_message=None)
        )
        runner = DefaultAnalyzeMarketRunner(job_runner=mock_job_runner)

        await runner.run(
            AnalyzeMarketRequest(market_index="QQQ", lookback_days=90, include_vix=False)
        )

        job = mock_job_runner.run.call_args[0][0]
        context = mock_job_runner.run.call_args[0][1]
        assert job.scope == JobScope.MARKET
        assert job.market_index == "QQQ"
        assert job.execution_type == MARKET_DETERMINISTIC_TYPE
        assert context["market_index"] == "QQQ"
        assert context["lookback_days"] == 90
        assert context["include_vix"] is False

    @pytest.mark.asyncio
    async def test_run_builds_question_driven_market_job(self) -> None:
        mock_job_runner = AsyncMock(spec=JobRunner)
        mock_job_runner.run = AsyncMock(
            return_value=RunJobResult(success=True, results={"analysis": "ok"}, error_message=None)
        )
        runner = DefaultAnalyzeMarketRunner(job_runner=mock_job_runner)

        await runner.run(
            AnalyzeMarketRequest(
                market_index="SPY",
                question="Is this risk on or risk off?",
                mode=AnalyzeMode.AUTO,
            )
        )

        job = mock_job_runner.run.call_args[0][0]
        context = mock_job_runner.run.call_args[0][1]
        assert job.scope == JobScope.MARKET
        assert job.market_index == "SPY"
        assert job.execution_type == MARKET_QUESTION_DRIVEN_TYPE
        assert context["question"] == "Is this risk on or risk off?"
