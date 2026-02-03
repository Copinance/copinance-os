"""Unit tests for workflow use case (one-off run)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from copinanceos.application.use_cases.workflow import (
    RunWorkflowRequest,
    RunWorkflowResponse,
    RunWorkflowUseCase,
)
from copinanceos.domain.models.job import JobScope, JobTimeframe
from copinanceos.domain.ports.workflows import WorkflowExecutor


@pytest.mark.unit
class TestRunWorkflowUseCase:
    """Test RunWorkflowUseCase."""

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        """Test successful one-off workflow run."""
        mock_executor = AsyncMock(spec=WorkflowExecutor)
        mock_executor.get_workflow_type = MagicMock(return_value="stock")
        mock_executor.validate = AsyncMock(return_value=True)
        mock_executor.execute = AsyncMock(
            return_value={"workflow_type": "stock", "stock_symbol": "AAPL"}
        )

        use_case = RunWorkflowUseCase(
            profile_repository=None,
            workflow_executors=[mock_executor],
        )
        response = await use_case.execute(
            RunWorkflowRequest(
                scope=JobScope.STOCK,
                stock_symbol="AAPL",
                timeframe=JobTimeframe.MID_TERM,
                workflow_type="stock",
            )
        )

        assert isinstance(response, RunWorkflowResponse)
        assert response.success is True
        assert response.results is not None
        assert response.results.get("stock_symbol") == "AAPL"
        assert response.error_message is None
