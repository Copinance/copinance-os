"""Unit tests for default job runner (one-off run)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from copinance_os.core.orchestrator.run_job import DefaultJobRunner
from copinance_os.domain.exceptions import RetryableExecutionError, ValidationError
from copinance_os.domain.models.analysis import MARKET_DETERMINISTIC_TYPE, AnalysisOutputMode
from copinance_os.domain.models.job import (
    Job,
    JobScope,
    JobTimeframe,
    ReportExclusionReason,
    RunJobResult,
)
from copinance_os.domain.models.market import MarketType
from copinance_os.domain.ports.analysis_execution import AnalysisExecutor
from copinance_os.research.workflows.analyze import INSTRUMENT_DETERMINISTIC_TYPE


@pytest.mark.unit
class TestDefaultJobRunner:
    """Test DefaultJobRunner."""

    @pytest.mark.asyncio
    async def test_run_success(self) -> None:
        """Test successful one-off job run."""
        mock_executor = AsyncMock(spec=AnalysisExecutor)
        mock_executor.get_executor_id = MagicMock(return_value="analyze_instrument")
        mock_executor.validate = AsyncMock(return_value=True)
        mock_executor.execute = AsyncMock(
            return_value={"execution_type": "analyze_instrument", "instrument_symbol": "AAPL"}
        )

        runner = DefaultJobRunner(
            profile_repository=None,
            analysis_executors=[mock_executor],
        )
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="AAPL",
            market_index=None,
            timeframe=JobTimeframe.MID_TERM,
            execution_type=INSTRUMENT_DETERMINISTIC_TYPE,
        )
        result = await runner.run(job, {"financial_literacy": "intermediate"})

        assert isinstance(result, RunJobResult)
        assert result.success is True
        assert result.results is not None
        assert result.results.get("instrument_symbol") == "AAPL"
        assert result.error_message is None
        mock_executor.execute.assert_called_once()
        call_job = mock_executor.execute.call_args[0][0]
        assert call_job.instrument_symbol == "AAPL"
        assert call_job.execution_type == INSTRUMENT_DETERMINISTIC_TYPE

    @pytest.mark.asyncio
    async def test_canonical_market_facts_need_no_literacy_and_build_no_report(self) -> None:
        mock_executor = AsyncMock(spec=AnalysisExecutor)
        mock_executor.validate = AsyncMock(return_value=True)
        mock_executor.execute = AsyncMock(return_value={"market_index": "SPY"})
        runner = DefaultJobRunner(profile_repository=None, analysis_executors=[mock_executor])
        job = Job(
            scope=JobScope.MARKET,
            market_type=None,
            instrument_symbol=None,
            market_index="SPY",
            timeframe=JobTimeframe.MID_TERM,
            execution_type=MARKET_DETERMINISTIC_TYPE,
        )

        result = await runner.run(
            job,
            {"output_mode": AnalysisOutputMode.CANONICAL_FACTS.value},
        )

        assert result.success is True
        assert result.report is None
        assert result.report_exclusion_reason == ReportExclusionReason.CANONICAL_FACTS

    @pytest.mark.asyncio
    async def test_adapted_job_without_literacy_is_rejected(self) -> None:
        mock_executor = AsyncMock(spec=AnalysisExecutor)
        mock_executor.validate = AsyncMock(return_value=True)
        runner = DefaultJobRunner(profile_repository=None, analysis_executors=[mock_executor])
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="AAPL",
            market_index=None,
            timeframe=JobTimeframe.MID_TERM,
            execution_type=INSTRUMENT_DETERMINISTIC_TYPE,
        )

        with pytest.raises(ValidationError, match="trusted request tier"):
            await runner.run(job, {})

        mock_executor.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_retries_then_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Transient domain errors trigger bounded retries."""

        async def _no_sleep(_delay: float) -> None:
            return None

        monkeypatch.setattr(
            "copinance_os.core.orchestrator.run_job.asyncio.sleep",
            _no_sleep,
        )

        mock_executor = AsyncMock(spec=AnalysisExecutor)
        mock_executor.get_executor_id = MagicMock(return_value="instrument_analysis")
        mock_executor.validate = AsyncMock(return_value=True)
        mock_executor.execute = AsyncMock(
            side_effect=[
                RetryableExecutionError("timeout"),
                {
                    "execution_type": "instrument_analysis",
                    "summary": {"text": "ok", "timeframe": "mid_term"},
                    "analysis": {"symbol": "AAPL", "timeframe": "mid_term"},
                },
            ]
        )

        runner = DefaultJobRunner(
            profile_repository=None,
            analysis_executors=[mock_executor],
            max_execute_retries=2,
        )
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="AAPL",
            market_index=None,
            timeframe=JobTimeframe.MID_TERM,
            execution_type=INSTRUMENT_DETERMINISTIC_TYPE,
        )
        result = await runner.run(job, {"financial_literacy": "intermediate"})

        assert result.success is True
        assert result.report is not None
        assert mock_executor.execute.await_count == 2
