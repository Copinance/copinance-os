"""Integration tests for core workflows (one-off run via RunWorkflowUseCase)."""

import pytest

from copinanceos.application.use_cases.workflow import RunWorkflowRequest
from copinanceos.domain.models.job import JobScope, JobTimeframe
from copinanceos.domain.ports.data_providers import FundamentalDataProvider
from copinanceos.infrastructure.containers import get_container


@pytest.mark.integration
class TestEndToEndWorkflow:
    """Test complete end-to-end workflows via run_workflow_use_case (no persistence)."""

    @pytest.mark.asyncio
    async def test_complete_stock_workflow(self) -> None:
        """Test stock workflow execution (one-off)."""
        container = get_container()
        use_case = container.run_workflow_use_case()

        response = await use_case.execute(
            RunWorkflowRequest(
                scope=JobScope.STOCK,
                stock_symbol="AAPL",
                timeframe=JobTimeframe.MID_TERM,
                workflow_type="stock",
            )
        )

        assert response.success is True
        assert response.results is not None
        assert len(response.results) > 0

    @pytest.mark.asyncio
    async def test_agentic_workflow_execution(self) -> None:
        """Test agent workflow execution (one-off)."""
        container = get_container()
        use_case = container.run_workflow_use_case()

        response = await use_case.execute(
            RunWorkflowRequest(
                scope=JobScope.STOCK,
                stock_symbol="MSFT",
                timeframe=JobTimeframe.SHORT_TERM,
                workflow_type="agent",
            )
        )

        assert response.success is True
        if response.results:
            results_status = response.results.get("status")
            if results_status == "completed":
                assert "agents_used" in response.results or "analysis" in response.results
            else:
                assert results_status == "failed"
                assert "error" in response.results
                assert "LLM analyzer not configured" in str(response.results.get("error", ""))

    @pytest.mark.asyncio
    async def test_static_workflow_with_fundamentals(
        self, fundamental_data_provider: FundamentalDataProvider
    ) -> None:
        """Test stock workflow execution includes full fundamentals data."""
        container = get_container()
        use_case = container.run_workflow_use_case()

        response = await use_case.execute(
            RunWorkflowRequest(
                scope=JobScope.STOCK,
                stock_symbol="AAPL",
                timeframe=JobTimeframe.MID_TERM,
                workflow_type="stock",
            )
        )

        assert response.success is True
        assert response.results is not None
        assert len(response.results) > 0

        results = response.results
        assert results["workflow_type"] == "stock"
        assert results["stock_symbol"] == "AAPL"
        assert "fundamentals" in results
        assert "company_name" in results["fundamentals"]
        assert "latest_income_statement" in results["fundamentals"]
        assert "latest_balance_sheet" in results["fundamentals"]
        assert "latest_cash_flow_statement" in results["fundamentals"]
