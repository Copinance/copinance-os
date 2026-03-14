"""Unit tests for default job runner (one-off run)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from copinanceos.application.run_job import DefaultJobRunner
from copinanceos.application.use_cases.analyze import INSTRUMENT_DETERMINISTIC_TYPE
from copinanceos.domain.models.job import Job, JobScope, JobTimeframe, RunJobResult
from copinanceos.domain.models.market import MarketType
from copinanceos.domain.ports.analysis_execution import AnalysisExecutor


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
