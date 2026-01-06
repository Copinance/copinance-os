"""Integration tests for core workflows."""

import pytest

from copinanceos.application.use_cases.research import (
    CreateResearchRequest,
    CreateResearchUseCase,
    ExecuteResearchRequest,
    ExecuteResearchUseCase,
)
from copinanceos.domain.models.research import ResearchStatus, ResearchTimeframe
from copinanceos.domain.ports.data_providers import FundamentalDataProvider
from copinanceos.infrastructure.containers import get_container
from copinanceos.infrastructure.repositories import ResearchRepositoryImpl
from copinanceos.infrastructure.workflows import (
    AgenticWorkflowExecutor,
    StaticWorkflowExecutor,
)


@pytest.mark.integration
class TestEndToEndWorkflow:
    """Test complete end-to-end workflows."""

    @pytest.mark.asyncio
    async def test_complete_research_workflow(self) -> None:
        """Test complete research workflow from creation to execution."""
        research_repo = ResearchRepositoryImpl()
        executors = [StaticWorkflowExecutor(), AgenticWorkflowExecutor()]

        # Create research
        create_research_uc = CreateResearchUseCase(research_repo)
        research_response = await create_research_uc.execute(
            CreateResearchRequest(
                stock_symbol="AAPL",
                timeframe=ResearchTimeframe.MID_TERM,
                workflow_type="stock",
            )
        )

        assert research_response.research.stock_symbol == "AAPL"
        assert research_response.research.status == ResearchStatus.PENDING

        # Execute research
        execute_research_uc = ExecuteResearchUseCase(research_repo, None, executors)
        execute_response = await execute_research_uc.execute(
            ExecuteResearchRequest(research_id=research_response.research.id)
        )

        assert execute_response.success is True
        assert execute_response.research.status == ResearchStatus.COMPLETED
        assert len(execute_response.research.results) > 0

    @pytest.mark.asyncio
    async def test_agentic_workflow_execution(self) -> None:
        """Test agent workflow execution."""
        research_repo = ResearchRepositoryImpl()
        executors = [StaticWorkflowExecutor(), AgenticWorkflowExecutor()]

        # Create agent research
        create_research_uc = CreateResearchUseCase(research_repo)
        research_response = await create_research_uc.execute(
            CreateResearchRequest(
                stock_symbol="MSFT",
                timeframe=ResearchTimeframe.SHORT_TERM,
                workflow_type="agent",
            )
        )

        # Execute agent research
        execute_research_uc = ExecuteResearchUseCase(research_repo, None, executors)
        execute_response = await execute_research_uc.execute(
            ExecuteResearchRequest(research_id=research_response.research.id)
        )

        # Note: Agentic workflow may fail if LLM analyzer is not configured
        # In that case, it will still complete but with an error in results
        assert execute_response.success is True
        # Check the results status, not the research entity status
        # The research entity status may be COMPLETED even if workflow results indicate failure
        results_status = execute_response.research.results.get("status")
        if results_status == "completed":
            # LLM analyzer is configured and workflow completed successfully
            assert "agents_used" in execute_response.research.results
        else:
            # LLM analyzer not configured - workflow failed gracefully
            assert results_status == "failed"
            assert "error" in execute_response.research.results
            assert "LLM analyzer not configured" in str(
                execute_response.research.results.get("error", "")
            )

    @pytest.mark.asyncio
    async def test_static_workflow_with_fundamentals(
        self, fundamental_data_provider: FundamentalDataProvider
    ) -> None:
        """Test stock workflow execution includes full fundamentals data."""
        container = get_container()
        research_repo = ResearchRepositoryImpl()
        executors = [
            StaticWorkflowExecutor(
                get_stock_use_case=container.get_stock_use_case(),
                market_data_provider=container.market_data_provider(),
                fundamentals_use_case=container.research_stock_fundamentals_use_case(),
            ),
            AgenticWorkflowExecutor(),
        ]

        # Create stock research (which now includes full fundamentals)
        create_research_uc = CreateResearchUseCase(research_repo)
        research_response = await create_research_uc.execute(
            CreateResearchRequest(
                stock_symbol="AAPL",
                timeframe=ResearchTimeframe.MID_TERM,
                workflow_type="stock",
            )
        )

        assert research_response.research.stock_symbol == "AAPL"
        assert research_response.research.status == ResearchStatus.PENDING

        # Execute stock research
        execute_research_uc = ExecuteResearchUseCase(research_repo, None, executors)
        execute_response = await execute_research_uc.execute(
            ExecuteResearchRequest(research_id=research_response.research.id)
        )

        assert execute_response.success is True
        assert execute_response.research.status == ResearchStatus.COMPLETED
        assert len(execute_response.research.results) > 0

        # Verify stock workflow includes fundamentals data
        results = execute_response.research.results
        assert results["workflow_type"] == "stock"
        assert results["stock_symbol"] == "AAPL"
        assert "fundamentals" in results
        assert "company_name" in results["fundamentals"]
        assert "latest_income_statement" in results["fundamentals"]
        assert "latest_balance_sheet" in results["fundamentals"]
        assert "latest_cash_flow_statement" in results["fundamentals"]
