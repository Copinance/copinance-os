"""Unit tests for base workflow executor."""

from uuid import uuid4

import pytest

from copinanceos.domain.models.job import Job, JobScope, JobTimeframe
from copinanceos.infrastructure.workflows.base import BaseWorkflowExecutor


class ConcreteWorkflowExecutor(BaseWorkflowExecutor):
    """Concrete implementation of BaseWorkflowExecutor for testing."""

    def __init__(self, should_fail: bool = False) -> None:
        """Initialize concrete executor."""
        self.should_fail = should_fail

    def get_workflow_type(self) -> str:
        """Get workflow type."""
        return "test_workflow"

    async def validate(self, job: Job) -> bool:
        """Validate job."""
        return job.workflow_type == "test_workflow"

    async def _execute_workflow(self, job: Job, context: dict) -> dict:
        """Execute workflow."""
        if self.should_fail:
            raise ValueError("Test error")
        return {
            "result": "success",
            "data": {"symbol": job.stock_symbol},
        }


@pytest.mark.unit
class TestBaseWorkflowExecutor:
    """Test BaseWorkflowExecutor."""

    def test_get_workflow_type(self) -> None:
        """Test that get_workflow_type is abstract."""
        executor = ConcreteWorkflowExecutor()
        assert executor.get_workflow_type() == "test_workflow"

    async def test_validate(self) -> None:
        """Test validate method."""
        executor = ConcreteWorkflowExecutor()
        job = Job(
            id=uuid4(),
            scope=JobScope.STOCK,
            stock_symbol="AAPL",
            timeframe=JobTimeframe.MID_TERM,
            workflow_type="test_workflow",
        )

        result = await executor.validate(job)
        assert result is True

        job.workflow_type = "other_workflow"
        result = await executor.validate(job)
        assert result is False

    def test_initialize_results(self) -> None:
        """Test _initialize_results method."""
        executor = ConcreteWorkflowExecutor()
        job = Job(
            id=uuid4(),
            scope=JobScope.STOCK,
            stock_symbol="AAPL",
            timeframe=JobTimeframe.MID_TERM,
            workflow_type="test_workflow",
        )

        results = executor._initialize_results(job, "test_workflow")

        assert results["workflow_type"] == "test_workflow"
        assert results["stock_symbol"] == "AAPL"
        assert results["timeframe"] == "mid_term"
        assert results["analysis_type"] == "test_workflow"
        assert "execution_timestamp" in results

    async def test_execute_success(self) -> None:
        """Test execute method with successful workflow."""
        executor = ConcreteWorkflowExecutor(should_fail=False)
        job = Job(
            id=uuid4(),
            scope=JobScope.STOCK,
            stock_symbol="AAPL",
            timeframe=JobTimeframe.MID_TERM,
            workflow_type="test_workflow",
        )
        context = {"key": "value"}

        results = await executor.execute(job, context)

        assert results["workflow_type"] == "test_workflow"
        assert results["stock_symbol"] == "AAPL"
        assert results["timeframe"] == "mid_term"
        assert results["status"] == "completed"
        assert results["message"] == "Test_workflow workflow executed successfully"
        assert results["result"] == "success"
        assert results["data"]["symbol"] == "AAPL"

    async def test_execute_with_custom_status(self) -> None:
        """Test execute method when workflow sets custom status."""
        executor = ConcreteWorkflowExecutor(should_fail=False)
        job = Job(
            id=uuid4(),
            scope=JobScope.STOCK,
            stock_symbol="AAPL",
            timeframe=JobTimeframe.MID_TERM,
            workflow_type="test_workflow",
        )

        # Override _execute_workflow to return custom status
        async def custom_execute(job: Job, context: dict) -> dict:
            return {"status": "custom_status", "message": "Custom message"}

        executor._execute_workflow = custom_execute
        results = await executor.execute(job, {})

        assert results["status"] == "custom_status"
        assert results["message"] == "Custom message"

    async def test_execute_failure(self) -> None:
        """Test execute method with failed workflow."""
        executor = ConcreteWorkflowExecutor(should_fail=True)
        job = Job(
            id=uuid4(),
            scope=JobScope.STOCK,
            stock_symbol="AAPL",
            timeframe=JobTimeframe.MID_TERM,
            workflow_type="test_workflow",
        )
        context = {"key": "value"}

        results = await executor.execute(job, context)

        assert results["workflow_type"] == "test_workflow"
        assert results["stock_symbol"] == "AAPL"
        assert results["status"] == "failed"
        assert "error" in results
        assert results["error"] == "Test error"
        assert "Test_workflow workflow execution failed" in results["message"]

    async def test_execute_uppercase_symbol(self) -> None:
        """Test that execute converts symbol to uppercase."""
        executor = ConcreteWorkflowExecutor(should_fail=False)
        job = Job(
            id=uuid4(),
            scope=JobScope.STOCK,
            stock_symbol="aapl",
            timeframe=JobTimeframe.MID_TERM,
            workflow_type="test_workflow",
        )

        results = await executor.execute(job, {})

        assert results["stock_symbol"] == "AAPL"

    async def test_execute_different_timeframes(self) -> None:
        """Test execute with different timeframes."""
        executor = ConcreteWorkflowExecutor(should_fail=False)

        for timeframe in JobTimeframe:
            job = Job(
                id=uuid4(),
                scope=JobScope.STOCK,
                stock_symbol="AAPL",
                timeframe=timeframe,
                workflow_type="test_workflow",
            )

            results = await executor.execute(job, {})

            assert results["timeframe"] == timeframe.value
            assert results["status"] == "completed"
