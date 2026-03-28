"""Unit tests for default job runner (one-off run)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from copinance_os.core.orchestrator.run_job import DefaultJobRunner
from copinance_os.domain.exceptions import RetryableExecutionError
from copinance_os.domain.models.job import Job, JobScope, JobTimeframe, RunJobResult
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
        result = await runner.run(job, {})

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
        result = await runner.run(job, {})

        assert result.success is True
        assert result.report is not None
        assert mock_executor.execute.await_count == 2
