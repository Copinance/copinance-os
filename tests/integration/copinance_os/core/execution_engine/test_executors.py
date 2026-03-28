"""Integration tests for analysis executors (one-off run via ResearchOrchestrator)."""

import pytest

from copinance_os.domain.models.job import Job, JobScope, JobTimeframe
from copinance_os.domain.models.market import MarketType
from copinance_os.domain.ports.data_providers import FundamentalDataProvider
from copinance_os.infra.di import get_container
from copinance_os.research.workflows.analyze import (
    INSTRUMENT_DETERMINISTIC_TYPE,
    INSTRUMENT_QUESTION_DRIVEN_TYPE,
)


@pytest.mark.integration
class TestEndToEndExecutors:
    """Test complete end-to-end analysis execution via ResearchOrchestrator (no persistence)."""

    @pytest.mark.asyncio
    async def test_complete_equity_analysis(self) -> None:
        """Test equity analysis execution (one-off)."""
        container = get_container()
        runner = container.research_orchestrator()

        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="AAPL",
            market_index=None,
            timeframe=JobTimeframe.MID_TERM,
            execution_type=INSTRUMENT_DETERMINISTIC_TYPE,
        )
        response = await runner.run_job(job, {})

        assert response.success is True
        assert response.results is not None
        assert len(response.results) > 0

    @pytest.mark.asyncio
    async def test_question_driven_analysis_execution(self) -> None:
        """Test question-driven analysis execution (one-off)."""
        container = get_container()
        runner = container.research_orchestrator()

        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="MSFT",
            market_index=None,
            timeframe=JobTimeframe.SHORT_TERM,
            execution_type=INSTRUMENT_QUESTION_DRIVEN_TYPE,
        )
        # Pass a question so execution reaches the LLM check; without it we get "Question is required" first
        context = {"question": "What is the short-term outlook for MSFT?"}
        response = await runner.run_job(job, context)

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
    async def test_deterministic_analysis_with_fundamentals(
        self, fundamental_data_provider: FundamentalDataProvider
    ) -> None:
        """Test equity analysis execution includes fundamentals data."""
        container = get_container()
        runner = container.research_orchestrator()

        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="AAPL",
            market_index=None,
            timeframe=JobTimeframe.MID_TERM,
            execution_type=INSTRUMENT_DETERMINISTIC_TYPE,
        )
        response = await runner.run_job(job, {})

        assert response.success is True
        assert response.results is not None
        assert len(response.results) > 0

        results = response.results
        assert results["execution_type"] == "instrument_analysis"
        assert results["instrument_symbol"] == "AAPL"
        assert "fundamentals" in results
        assert "company_name" in results["fundamentals"]
