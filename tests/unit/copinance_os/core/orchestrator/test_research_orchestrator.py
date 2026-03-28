"""Unit tests for ResearchOrchestrator."""

from unittest.mock import AsyncMock

import pytest

from copinance_os.core.orchestrator.research_orchestrator import ResearchOrchestrator
from copinance_os.core.orchestrator.run_job import DefaultJobRunner
from copinance_os.domain.models.job import Job, JobScope, JobTimeframe, RunJobResult
from copinance_os.domain.models.market import MarketType
from copinance_os.domain.ports.analysis_execution import JobRunner
from copinance_os.research.workflows.analyze import INSTRUMENT_DETERMINISTIC_TYPE
from copinance_os.research.workflows.backtest import SimpleLongOnlyWorkflowRequest


@pytest.mark.unit
class TestResearchOrchestrator:
    @pytest.mark.asyncio
    async def test_run_job_delegates(self) -> None:
        mock_runner = AsyncMock(spec=JobRunner)
        mock_runner.run = AsyncMock(
            return_value=RunJobResult(success=True, results={"x": 1}, error_message=None)
        )
        orch = ResearchOrchestrator(mock_runner)
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="AAPL",
            market_index=None,
            timeframe=JobTimeframe.MID_TERM,
            execution_type=INSTRUMENT_DETERMINISTIC_TYPE,
        )
        ctx = {"question": None}
        out = await orch.run_job(job, ctx)
        assert out.success is True
        mock_runner.run.assert_awaited_once_with(job, ctx)

    @pytest.mark.unit
    def test_run_simple_long_only_backtest(self) -> None:
        orch = ResearchOrchestrator(
            DefaultJobRunner(profile_repository=None, analysis_executors=[])
        )
        req = SimpleLongOnlyWorkflowRequest(
            closes=[100.0, 110.0],
            weights=[1.0, 1.0],
            strategy_id="s",
            initial_cash=1000.0,
        )
        result = orch.run_simple_long_only_backtest(req)
        assert result.equity_curve[-1] == pytest.approx(1100.0)
