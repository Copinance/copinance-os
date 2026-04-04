"""Unit tests for progressive analyze use cases and default runners."""

from unittest.mock import AsyncMock

import pytest

from copinance_os.core.orchestrator.research_orchestrator import ResearchOrchestrator
from copinance_os.core.orchestrator.runners import (
    DefaultAnalyzeInstrumentRunner,
    DefaultAnalyzeMarketRunner,
)
from copinance_os.domain.models.job import JobScope, JobTimeframe, RunJobResult
from copinance_os.domain.models.llm_conversation import LLMConversationTurn
from copinance_os.domain.models.market import MarketType, OptionSide
from copinance_os.domain.ports.analysis_execution import JobRunner
from copinance_os.research.workflows.analyze import (
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
        runner = DefaultAnalyzeInstrumentRunner(
            research_orchestrator=ResearchOrchestrator(mock_job_runner)
        )

        await runner.run(AnalyzeInstrumentRequest(symbol="AAPL"))

        job = mock_job_runner.run.call_args[0][0]
        context = mock_job_runner.run.call_args[0][1]
        assert job.scope == JobScope.INSTRUMENT
        assert job.market_type == MarketType.EQUITY
        assert job.instrument_symbol == "AAPL"
        assert job.execution_type == INSTRUMENT_DETERMINISTIC_TYPE
        assert job.timeframe == JobTimeframe.MID_TERM
        assert context["question"] is None
        assert context["stream"] is False
        assert context["no_cache"] is False

    @pytest.mark.asyncio
    async def test_run_builds_agentic_options_job(self) -> None:
        mock_job_runner = AsyncMock(spec=JobRunner)
        mock_job_runner.run = AsyncMock(
            return_value=RunJobResult(success=True, results={}, error_message=None)
        )
        runner = DefaultAnalyzeInstrumentRunner(
            research_orchestrator=ResearchOrchestrator(mock_job_runner)
        )

        await runner.run(
            AnalyzeInstrumentRequest(
                symbol="AAPL",
                market_type=MarketType.OPTIONS,
                question="Is skew bearish?",
                mode=AnalyzeMode.AUTO,
                expiration_date="2026-06-19",
                expiration_dates=None,
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
        assert context["expiration_dates"] == ["2026-06-19"]
        assert context["option_side"] == "call"
        assert context["stream"] is False

    @pytest.mark.asyncio
    async def test_run_passes_stream_in_context(self) -> None:
        mock_job_runner = AsyncMock(spec=JobRunner)
        mock_job_runner.run = AsyncMock(
            return_value=RunJobResult(success=True, results={}, error_message=None)
        )
        runner = DefaultAnalyzeInstrumentRunner(
            research_orchestrator=ResearchOrchestrator(mock_job_runner)
        )
        await runner.run(
            AnalyzeInstrumentRequest(
                symbol="AAPL",
                question="Test?",
                mode=AnalyzeMode.QUESTION_DRIVEN,
                stream=True,
            )
        )
        context = mock_job_runner.run.call_args[0][1]
        assert context["stream"] is True

    @pytest.mark.asyncio
    async def test_run_passes_no_cache_in_context(self) -> None:
        mock_job_runner = AsyncMock(spec=JobRunner)
        mock_job_runner.run = AsyncMock(
            return_value=RunJobResult(success=True, results={}, error_message=None)
        )
        runner = DefaultAnalyzeInstrumentRunner(
            research_orchestrator=ResearchOrchestrator(mock_job_runner)
        )
        await runner.run(AnalyzeInstrumentRequest(symbol="AAPL", no_cache=True))
        context = mock_job_runner.run.call_args[0][1]
        assert context["no_cache"] is True


@pytest.mark.unit
def test_instrument_request_rejects_conversation_in_deterministic_mode() -> None:
    with pytest.raises(ValueError, match="conversation_history"):
        AnalyzeInstrumentRequest(
            symbol="AAPL",
            mode=AnalyzeMode.DETERMINISTIC,
            conversation_history=[
                LLMConversationTurn(role="user", content="a"),
                LLMConversationTurn(role="assistant", content="b"),
            ],
        )


@pytest.mark.unit
def test_instrument_request_rejects_invalid_conversation_pairs() -> None:
    with pytest.raises(ValueError, match="even length"):
        AnalyzeInstrumentRequest(
            symbol="AAPL",
            question="q",
            mode=AnalyzeMode.QUESTION_DRIVEN,
            conversation_history=[LLMConversationTurn(role="user", content="only user")],
        )


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
        runner = DefaultAnalyzeMarketRunner(
            research_orchestrator=ResearchOrchestrator(mock_job_runner)
        )

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
        assert context["stream"] is False
        assert context["no_cache"] is False

    @pytest.mark.asyncio
    async def test_run_builds_question_driven_market_job(self) -> None:
        mock_job_runner = AsyncMock(spec=JobRunner)
        mock_job_runner.run = AsyncMock(
            return_value=RunJobResult(success=True, results={"analysis": "ok"}, error_message=None)
        )
        runner = DefaultAnalyzeMarketRunner(
            research_orchestrator=ResearchOrchestrator(mock_job_runner)
        )

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
        assert context["stream"] is False

    @pytest.mark.asyncio
    async def test_run_passes_no_cache_in_context(self) -> None:
        mock_job_runner = AsyncMock(spec=JobRunner)
        mock_job_runner.run = AsyncMock(
            return_value=RunJobResult(success=True, results={}, error_message=None)
        )
        runner = DefaultAnalyzeMarketRunner(
            research_orchestrator=ResearchOrchestrator(mock_job_runner)
        )
        await runner.run(AnalyzeMarketRequest(market_index="SPY", no_cache=True))
        context = mock_job_runner.run.call_args[0][1]
        assert context["no_cache"] is True
