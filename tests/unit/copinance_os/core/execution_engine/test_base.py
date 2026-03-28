"""Unit tests for base analysis executor."""

from uuid import uuid4

import pytest

from copinance_os.core.execution_engine.base import BaseAnalysisExecutor
from copinance_os.domain.models.job import Job, JobScope, JobTimeframe


class ConcreteAnalysisExecutor(BaseAnalysisExecutor):
    """Concrete implementation for testing."""

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def get_executor_id(self) -> str:
        return "test_executor"

    async def validate(self, job: Job) -> bool:
        return job.execution_type == "test_executor"

    async def _execute_analysis(self, job: Job, context: dict) -> dict:
        if self.should_fail:
            raise ValueError("Test error")
        return {
            "result": "success",
            "data": {"symbol": job.instrument_symbol},
        }


@pytest.mark.unit
class TestBaseAnalysisExecutor:
    """Test BaseAnalysisExecutor."""

    def test_get_executor_id(self) -> None:
        executor = ConcreteAnalysisExecutor()
        assert executor.get_executor_id() == "test_executor"

    async def test_validate(self) -> None:
        executor = ConcreteAnalysisExecutor()
        job = Job(
            id=uuid4(),
            scope=JobScope.INSTRUMENT,
            instrument_symbol="AAPL",
            timeframe=JobTimeframe.MID_TERM,
            execution_type="test_executor",
        )
        result = await executor.validate(job)
        assert result is True
        job.execution_type = "other"
        result = await executor.validate(job)
        assert result is False

    def test_initialize_results(self) -> None:
        executor = ConcreteAnalysisExecutor()
        job = Job(
            id=uuid4(),
            scope=JobScope.INSTRUMENT,
            instrument_symbol="AAPL",
            timeframe=JobTimeframe.MID_TERM,
            execution_type="test_executor",
        )
        results = executor._initialize_results(job, "test_executor")
        assert results["execution_type"] == "test_executor"
        assert results["instrument_symbol"] == "AAPL"
        assert results["timeframe"] == "mid_term"
        assert results["execution_mode"] == "deterministic"
        assert "execution_timestamp" in results

    async def test_execute_success(self) -> None:
        executor = ConcreteAnalysisExecutor(should_fail=False)
        job = Job(
            id=uuid4(),
            scope=JobScope.INSTRUMENT,
            instrument_symbol="AAPL",
            timeframe=JobTimeframe.MID_TERM,
            execution_type="test_executor",
        )
        context = {"key": "value"}
        results = await executor.execute(job, context)
        assert results["execution_type"] == "test_executor"
        assert results["instrument_symbol"] == "AAPL"
        assert results["timeframe"] == "mid_term"
        assert results["status"] == "completed"
        assert results["message"] == "Analysis executed successfully"
        assert results["result"] == "success"
        assert results["data"]["symbol"] == "AAPL"

    async def test_execute_with_custom_status(self) -> None:
        executor = ConcreteAnalysisExecutor(should_fail=False)
        job = Job(
            id=uuid4(),
            scope=JobScope.INSTRUMENT,
            instrument_symbol="AAPL",
            timeframe=JobTimeframe.MID_TERM,
            execution_type="test_executor",
        )

        async def custom_execute(job: Job, context: dict) -> dict:
            return {"status": "custom_status", "message": "Custom message"}

        executor._execute_analysis = custom_execute
        results = await executor.execute(job, {})
        assert results["status"] == "custom_status"
        assert results["message"] == "Custom message"

    async def test_execute_failure(self) -> None:
        executor = ConcreteAnalysisExecutor(should_fail=True)
        job = Job(
            id=uuid4(),
            scope=JobScope.INSTRUMENT,
            instrument_symbol="AAPL",
            timeframe=JobTimeframe.MID_TERM,
            execution_type="test_executor",
        )
        context = {"key": "value"}
        results = await executor.execute(job, context)
        assert results["execution_type"] == "test_executor"
        assert results["instrument_symbol"] == "AAPL"
        assert results["status"] == "failed"
        assert "error" in results
        assert results["error"] == "Test error"
        assert "Analysis execution failed" in results["message"]

    async def test_execute_uppercase_symbol(self) -> None:
        executor = ConcreteAnalysisExecutor(should_fail=False)
        job = Job(
            id=uuid4(),
            scope=JobScope.INSTRUMENT,
            instrument_symbol="aapl",
            timeframe=JobTimeframe.MID_TERM,
            execution_type="test_executor",
        )
        results = await executor.execute(job, {})
        assert results["instrument_symbol"] == "AAPL"

    async def test_execute_different_timeframes(self) -> None:
        executor = ConcreteAnalysisExecutor(should_fail=False)
        for timeframe in JobTimeframe:
            job = Job(
                id=uuid4(),
                scope=JobScope.INSTRUMENT,
                instrument_symbol="AAPL",
                timeframe=timeframe,
                execution_type="test_executor",
            )
            results = await executor.execute(job, {})
            assert results["timeframe"] == timeframe.value
            assert results["status"] == "completed"
