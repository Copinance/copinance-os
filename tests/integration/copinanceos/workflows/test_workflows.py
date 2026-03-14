"""Integration tests for core workflows (one-off run via JobRunner)."""

import pytest

from copinanceos.domain.models.job import Job, JobScope, JobTimeframe
from copinanceos.domain.models.market import MarketType
from copinanceos.domain.ports.data_providers import FundamentalDataProvider
from copinanceos.infrastructure.containers import get_container


@pytest.mark.integration
class TestEndToEndWorkflow:
    """Test complete end-to-end workflows via job_runner (no persistence)."""

    @pytest.mark.asyncio
    async def test_complete_equity_workflow(self) -> None:
        """Test equity workflow execution (one-off)."""
        container = get_container()
        runner = container.job_runner()

        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="AAPL",
            market_index=None,
            timeframe=JobTimeframe.MID_TERM,
            workflow_type="equity",
        )
        response = await runner.run(job, {})

        assert response.success is True
        assert response.results is not None
        assert len(response.results) > 0

    @pytest.mark.asyncio
    async def test_agentic_workflow_execution(self) -> None:
        """Test agent workflow execution (one-off)."""
        container = get_container()
        runner = container.job_runner()

        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="MSFT",
            market_index=None,
            timeframe=JobTimeframe.SHORT_TERM,
            workflow_type="agent",
        )
        response = await runner.run(job, {})

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
        """Test equity workflow execution includes fundamentals data."""
        container = get_container()
        runner = container.job_runner()

        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="AAPL",
            market_index=None,
            timeframe=JobTimeframe.MID_TERM,
            workflow_type="equity",
        )
        response = await runner.run(job, {})

        assert response.success is True
        assert response.results is not None
        assert len(response.results) > 0

        results = response.results
        assert results["workflow_type"] == "equity"
        assert results["instrument_symbol"] == "AAPL"
        assert "fundamentals" in results
        assert "company_name" in results["fundamentals"]
        # Static workflow fundamentals include company_name, symbol, ratios, etc. (no statement keys)
