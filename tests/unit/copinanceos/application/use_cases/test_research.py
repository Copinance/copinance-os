"""Unit tests for research use cases."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from copinanceos.application.use_cases.research import (
    CreateResearchRequest,
    CreateResearchResponse,
    CreateResearchUseCase,
    ExecuteResearchRequest,
    ExecuteResearchResponse,
    ExecuteResearchUseCase,
    GetResearchRequest,
    GetResearchResponse,
    GetResearchUseCase,
    SetResearchContextRequest,
    SetResearchContextResponse,
    SetResearchContextUseCase,
)
from copinanceos.domain.exceptions import (
    ProfileNotFoundError,
    ResearchNotFoundError,
    WorkflowNotFoundError,
)
from copinanceos.domain.models.research import Research, ResearchStatus, ResearchTimeframe
from copinanceos.domain.models.research_profile import FinancialLiteracy, ResearchProfile
from copinanceos.domain.ports.repositories import (
    ResearchProfileRepository,
    ResearchRepository,
)
from copinanceos.domain.ports.workflows import WorkflowExecutor


@pytest.mark.unit
class TestCreateResearchUseCase:
    """Test CreateResearchUseCase."""

    def test_initialization(self) -> None:
        """Test use case initialization."""
        mock_repository = MagicMock(spec=ResearchRepository)
        use_case = CreateResearchUseCase(research_repository=mock_repository)
        assert use_case._research_repository is mock_repository

    @pytest.mark.asyncio
    async def test_execute_with_all_fields(self) -> None:
        """Test execute with all fields provided."""
        mock_repository = AsyncMock(spec=ResearchRepository)
        profile_id = uuid4()
        research = Research(
            id=uuid4(),
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            parameters={"key": "value"},
            profile_id=profile_id,
        )
        mock_repository.save = AsyncMock(return_value=research)

        use_case = CreateResearchUseCase(research_repository=mock_repository)
        request = CreateResearchRequest(
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            parameters={"key": "value"},
            profile_id=profile_id,
        )
        response = await use_case.execute(request)

        assert isinstance(response, CreateResearchResponse)
        assert response.research.stock_symbol == "AAPL"
        assert response.research.timeframe == ResearchTimeframe.MID_TERM
        assert response.research.workflow_type == "stock"
        assert response.research.parameters == {"key": "value"}
        assert response.research.profile_id == profile_id
        assert response.research.status == ResearchStatus.PENDING
        assert response.research.error_message is None
        mock_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_minimal_fields(self) -> None:
        """Test execute with minimal required fields."""
        mock_repository = AsyncMock(spec=ResearchRepository)
        research = Research(
            id=uuid4(),
            stock_symbol="MSFT",
            timeframe=ResearchTimeframe.SHORT_TERM,
            workflow_type="agent",
        )
        mock_repository.save = AsyncMock(return_value=research)

        use_case = CreateResearchUseCase(research_repository=mock_repository)
        request = CreateResearchRequest(
            stock_symbol="MSFT",
            timeframe=ResearchTimeframe.SHORT_TERM,
            workflow_type="agent",
        )
        response = await use_case.execute(request)

        assert response.research.stock_symbol == "MSFT"
        assert response.research.timeframe == ResearchTimeframe.SHORT_TERM
        assert response.research.workflow_type == "agent"
        assert response.research.parameters == {}
        assert response.research.profile_id is None
        assert response.research.status == ResearchStatus.PENDING
        mock_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_empty_parameters(self) -> None:
        """Test execute with empty parameters dict."""
        mock_repository = AsyncMock(spec=ResearchRepository)
        research = Research(
            id=uuid4(),
            stock_symbol="GOOGL",
            timeframe=ResearchTimeframe.LONG_TERM,
            workflow_type="stock",
            parameters={},
        )
        mock_repository.save = AsyncMock(return_value=research)

        use_case = CreateResearchUseCase(research_repository=mock_repository)
        request = CreateResearchRequest(
            stock_symbol="GOOGL",
            timeframe=ResearchTimeframe.LONG_TERM,
            workflow_type="stock",
            parameters={},
        )
        response = await use_case.execute(request)

        assert response.research.parameters == {}
        mock_repository.save.assert_called_once()


@pytest.mark.unit
class TestGetResearchUseCase:
    """Test GetResearchUseCase."""

    def test_initialization(self) -> None:
        """Test use case initialization."""
        mock_repository = MagicMock(spec=ResearchRepository)
        use_case = GetResearchUseCase(research_repository=mock_repository)
        assert use_case._research_repository is mock_repository

    @pytest.mark.asyncio
    async def test_execute_research_found(self) -> None:
        """Test execute when research is found."""
        mock_repository = AsyncMock(spec=ResearchRepository)
        research_id = uuid4()
        research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
        )
        mock_repository.get_by_id = AsyncMock(return_value=research)

        use_case = GetResearchUseCase(research_repository=mock_repository)
        request = GetResearchRequest(research_id=research_id)
        response = await use_case.execute(request)

        assert isinstance(response, GetResearchResponse)
        assert response.research is not None
        assert response.research.id == research_id
        assert response.research.stock_symbol == "AAPL"
        mock_repository.get_by_id.assert_called_once_with(research_id)

    @pytest.mark.asyncio
    async def test_execute_research_not_found(self) -> None:
        """Test execute when research is not found."""
        mock_repository = AsyncMock(spec=ResearchRepository)
        research_id = uuid4()
        mock_repository.get_by_id = AsyncMock(return_value=None)

        use_case = GetResearchUseCase(research_repository=mock_repository)
        request = GetResearchRequest(research_id=research_id)
        response = await use_case.execute(request)

        assert isinstance(response, GetResearchResponse)
        assert response.research is None
        mock_repository.get_by_id.assert_called_once_with(research_id)


@pytest.mark.unit
class TestSetResearchContextUseCase:
    """Test SetResearchContextUseCase."""

    def test_initialization(self) -> None:
        """Test use case initialization."""
        mock_research_repo = MagicMock(spec=ResearchRepository)
        mock_profile_repo = MagicMock(spec=ResearchProfileRepository)
        use_case = SetResearchContextUseCase(
            research_repository=mock_research_repo,
            profile_repository=mock_profile_repo,
        )
        assert use_case._research_repository is mock_research_repo
        assert use_case._profile_repository is mock_profile_repo

    @pytest.mark.asyncio
    async def test_execute_with_profile_id(self) -> None:
        """Test execute with profile_id set."""
        mock_research_repo = AsyncMock(spec=ResearchRepository)
        mock_profile_repo = AsyncMock(spec=ResearchProfileRepository)
        research_id = uuid4()
        profile_id = uuid4()

        research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            profile_id=None,
        )
        profile = ResearchProfile(
            id=profile_id,
            financial_literacy=FinancialLiteracy.INTERMEDIATE,
            preferences={"key": "value"},
        )
        updated_research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            profile_id=profile_id,
        )

        mock_research_repo.get_by_id = AsyncMock(return_value=research)
        mock_profile_repo.get_by_id = AsyncMock(return_value=profile)
        mock_research_repo.save = AsyncMock(return_value=updated_research)

        use_case = SetResearchContextUseCase(
            research_repository=mock_research_repo,
            profile_repository=mock_profile_repo,
        )
        request = SetResearchContextRequest(
            research_id=research_id,
            profile_id=profile_id,
        )
        response = await use_case.execute(request)

        assert isinstance(response, SetResearchContextResponse)
        assert response.research.id == research_id
        assert response.research.profile_id == profile_id
        mock_research_repo.get_by_id.assert_called_once_with(research_id)
        mock_profile_repo.get_by_id.assert_called_once_with(profile_id)
        mock_research_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_without_profile_id(self) -> None:
        """Test execute with profile_id set to None."""
        mock_research_repo = AsyncMock(spec=ResearchRepository)
        mock_profile_repo = AsyncMock(spec=ResearchProfileRepository)
        research_id = uuid4()

        research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            profile_id=uuid4(),
        )
        updated_research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            profile_id=None,
        )

        mock_research_repo.get_by_id = AsyncMock(return_value=research)
        mock_research_repo.save = AsyncMock(return_value=updated_research)

        use_case = SetResearchContextUseCase(
            research_repository=mock_research_repo,
            profile_repository=mock_profile_repo,
        )
        request = SetResearchContextRequest(
            research_id=research_id,
            profile_id=None,
        )
        response = await use_case.execute(request)

        assert response.research.profile_id is None
        mock_research_repo.get_by_id.assert_called_once_with(research_id)
        mock_profile_repo.get_by_id.assert_not_called()
        mock_research_repo.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_research_not_found(self) -> None:
        """Test execute when research is not found."""
        mock_research_repo = AsyncMock(spec=ResearchRepository)
        mock_profile_repo = AsyncMock(spec=ResearchProfileRepository)
        research_id = uuid4()

        mock_research_repo.get_by_id = AsyncMock(return_value=None)

        use_case = SetResearchContextUseCase(
            research_repository=mock_research_repo,
            profile_repository=mock_profile_repo,
        )
        request = SetResearchContextRequest(
            research_id=research_id,
            profile_id=None,
        )

        with pytest.raises(ResearchNotFoundError):
            await use_case.execute(request)

        mock_research_repo.get_by_id.assert_called_once_with(research_id)
        mock_profile_repo.get_by_id.assert_not_called()
        mock_research_repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_profile_not_found(self) -> None:
        """Test execute when profile is not found."""
        mock_research_repo = AsyncMock(spec=ResearchRepository)
        mock_profile_repo = AsyncMock(spec=ResearchProfileRepository)
        research_id = uuid4()
        profile_id = uuid4()

        research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
        )

        mock_research_repo.get_by_id = AsyncMock(return_value=research)
        mock_profile_repo.get_by_id = AsyncMock(return_value=None)

        use_case = SetResearchContextUseCase(
            research_repository=mock_research_repo,
            profile_repository=mock_profile_repo,
        )
        request = SetResearchContextRequest(
            research_id=research_id,
            profile_id=profile_id,
        )

        with pytest.raises(ProfileNotFoundError):
            await use_case.execute(request)

        mock_research_repo.get_by_id.assert_called_once_with(research_id)
        mock_profile_repo.get_by_id.assert_called_once_with(profile_id)
        mock_research_repo.save.assert_not_called()


@pytest.mark.unit
class TestExecuteResearchUseCase:
    """Test ExecuteResearchUseCase."""

    def test_initialization_without_profile_repository(self) -> None:
        """Test initialization without profile repository."""
        mock_research_repo = MagicMock(spec=ResearchRepository)
        mock_executors = [MagicMock(spec=WorkflowExecutor)]
        use_case = ExecuteResearchUseCase(
            research_repository=mock_research_repo,
            profile_repository=None,
            workflow_executors=mock_executors,
        )
        assert use_case._research_repository is mock_research_repo
        assert use_case._workflow_executors is mock_executors
        assert use_case._profile_repository is None

    def test_initialization_with_profile_repository(self) -> None:
        """Test initialization with profile repository."""
        mock_research_repo = MagicMock(spec=ResearchRepository)
        mock_profile_repo = MagicMock(spec=ResearchProfileRepository)
        mock_executors = [MagicMock(spec=WorkflowExecutor)]
        use_case = ExecuteResearchUseCase(
            research_repository=mock_research_repo,
            workflow_executors=mock_executors,
            profile_repository=mock_profile_repo,
        )
        assert use_case._research_repository is mock_research_repo
        assert use_case._workflow_executors is mock_executors
        assert use_case._profile_repository is mock_profile_repo

    @pytest.mark.asyncio
    async def test_execute_success(self) -> None:
        """Test successful execution."""
        mock_research_repo = AsyncMock(spec=ResearchRepository)
        research_id = uuid4()
        research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
        )
        updated_research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            status=ResearchStatus.COMPLETED,
            results={"result": "data"},
        )

        mock_executor = AsyncMock(spec=WorkflowExecutor)
        mock_executor.get_workflow_type = MagicMock(return_value="stock")
        mock_executor.validate = AsyncMock(return_value=True)
        mock_executor.execute = AsyncMock(return_value={"result": "data"})

        mock_research_repo.get_by_id = AsyncMock(return_value=research)
        mock_research_repo.save = AsyncMock(side_effect=[research, updated_research])

        use_case = ExecuteResearchUseCase(
            research_repository=mock_research_repo,
            profile_repository=None,
            workflow_executors=[mock_executor],
        )
        request = ExecuteResearchRequest(research_id=research_id, context={})
        response = await use_case.execute(request)

        assert isinstance(response, ExecuteResearchResponse)
        assert response.success is True
        assert response.research.status == ResearchStatus.COMPLETED
        assert response.research.results == {"result": "data"}
        assert mock_research_repo.save.call_count == 2  # Once for IN_PROGRESS, once for COMPLETED

    @pytest.mark.asyncio
    async def test_execute_research_not_found(self) -> None:
        """Test execute when research is not found."""
        mock_research_repo = AsyncMock(spec=ResearchRepository)
        research_id = uuid4()
        mock_research_repo.get_by_id = AsyncMock(return_value=None)

        mock_executor = AsyncMock(spec=WorkflowExecutor)
        use_case = ExecuteResearchUseCase(
            research_repository=mock_research_repo,
            profile_repository=None,
            workflow_executors=[mock_executor],
        )
        request = ExecuteResearchRequest(research_id=research_id, context={})

        with pytest.raises(ResearchNotFoundError):
            await use_case.execute(request)

        mock_research_repo.get_by_id.assert_called_once_with(research_id)
        mock_research_repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_no_executor_found(self) -> None:
        """Test execute when no matching executor is found."""
        mock_research_repo = AsyncMock(spec=ResearchRepository)
        research_id = uuid4()
        research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="unknown_workflow",
        )

        mock_executor = AsyncMock(spec=WorkflowExecutor)
        mock_executor.get_workflow_type = MagicMock(return_value="stock")
        mock_executor.validate = AsyncMock(return_value=False)

        mock_research_repo.get_by_id = AsyncMock(return_value=research)

        use_case = ExecuteResearchUseCase(
            research_repository=mock_research_repo,
            profile_repository=None,
            workflow_executors=[mock_executor],
        )
        request = ExecuteResearchRequest(research_id=research_id, context={})

        with pytest.raises(WorkflowNotFoundError):
            await use_case.execute(request)

        mock_research_repo.get_by_id.assert_called_once_with(research_id)
        mock_research_repo.save.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_with_profile_context(self) -> None:
        """Test execute with profile context."""
        mock_research_repo = AsyncMock(spec=ResearchRepository)
        mock_profile_repo = AsyncMock(spec=ResearchProfileRepository)
        research_id = uuid4()
        profile_id = uuid4()

        research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            profile_id=profile_id,
        )
        profile = ResearchProfile(
            id=profile_id,
            financial_literacy=FinancialLiteracy.ADVANCED,
            preferences={"pref1": "value1", "pref2": "value2"},
            display_name="Test Profile",
        )
        updated_research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            profile_id=profile_id,
            status=ResearchStatus.COMPLETED,
            results={"result": "data"},
        )

        mock_executor = AsyncMock(spec=WorkflowExecutor)
        mock_executor.get_workflow_type = MagicMock(return_value="stock")
        mock_executor.validate = AsyncMock(return_value=True)
        mock_executor.execute = AsyncMock(return_value={"result": "data"})

        mock_research_repo.get_by_id = AsyncMock(return_value=research)
        mock_profile_repo.get_by_id = AsyncMock(return_value=profile)
        mock_research_repo.save = AsyncMock(side_effect=[research, updated_research])

        use_case = ExecuteResearchUseCase(
            research_repository=mock_research_repo,
            workflow_executors=[mock_executor],
            profile_repository=mock_profile_repo,
        )
        request = ExecuteResearchRequest(research_id=research_id, context={"key": "value"})
        response = await use_case.execute(request)

        assert response.success is True
        # Verify executor was called with merged context
        call_args = mock_executor.execute.call_args
        execution_context = call_args[0][1]  # Second argument is context
        assert execution_context["key"] == "value"
        assert execution_context["financial_literacy"] == "advanced"
        assert execution_context["profile_preferences"] == {"pref1": "value1", "pref2": "value2"}
        assert execution_context["profile_display_name"] == "Test Profile"
        mock_profile_repo.get_by_id.assert_called_once_with(profile_id)

    @pytest.mark.asyncio
    async def test_execute_with_profile_id_but_no_profile_repository(self) -> None:
        """Test execute with profile_id but no profile repository."""
        mock_research_repo = AsyncMock(spec=ResearchRepository)
        research_id = uuid4()
        profile_id = uuid4()

        research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            profile_id=profile_id,
        )
        updated_research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            profile_id=profile_id,
            status=ResearchStatus.COMPLETED,
            results={"result": "data"},
        )

        mock_executor = AsyncMock(spec=WorkflowExecutor)
        mock_executor.get_workflow_type = MagicMock(return_value="stock")
        mock_executor.validate = AsyncMock(return_value=True)
        mock_executor.execute = AsyncMock(return_value={"result": "data"})

        mock_research_repo.get_by_id = AsyncMock(return_value=research)
        mock_research_repo.save = AsyncMock(side_effect=[research, updated_research])

        use_case = ExecuteResearchUseCase(
            research_repository=mock_research_repo,
            workflow_executors=[mock_executor],
            profile_repository=None,
        )
        request = ExecuteResearchRequest(research_id=research_id, context={})
        response = await use_case.execute(request)

        assert response.success is True
        # Verify executor was called with original context only
        call_args = mock_executor.execute.call_args
        execution_context = call_args[0][1]
        assert execution_context == {}
        assert "financial_literacy" not in execution_context

    @pytest.mark.asyncio
    async def test_execute_with_profile_id_but_profile_not_found(self) -> None:
        """Test execute with profile_id but profile not found."""
        mock_research_repo = AsyncMock(spec=ResearchRepository)
        mock_profile_repo = AsyncMock(spec=ResearchProfileRepository)
        research_id = uuid4()
        profile_id = uuid4()

        research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            profile_id=profile_id,
        )
        updated_research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            profile_id=profile_id,
            status=ResearchStatus.COMPLETED,
            results={"result": "data"},
        )

        mock_executor = AsyncMock(spec=WorkflowExecutor)
        mock_executor.get_workflow_type = MagicMock(return_value="stock")
        mock_executor.validate = AsyncMock(return_value=True)
        mock_executor.execute = AsyncMock(return_value={"result": "data"})

        mock_research_repo.get_by_id = AsyncMock(return_value=research)
        mock_profile_repo.get_by_id = AsyncMock(return_value=None)
        mock_research_repo.save = AsyncMock(side_effect=[research, updated_research])

        use_case = ExecuteResearchUseCase(
            research_repository=mock_research_repo,
            workflow_executors=[mock_executor],
            profile_repository=mock_profile_repo,
        )
        request = ExecuteResearchRequest(research_id=research_id, context={})
        response = await use_case.execute(request)

        # Should continue without profile context
        assert response.success is True
        call_args = mock_executor.execute.call_args
        execution_context = call_args[0][1]
        assert execution_context == {}
        assert "financial_literacy" not in execution_context

    @pytest.mark.asyncio
    async def test_execute_with_failure(self) -> None:
        """Test execute when workflow execution fails."""
        mock_research_repo = AsyncMock(spec=ResearchRepository)
        research_id = uuid4()
        research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
        )
        failed_research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            status=ResearchStatus.FAILED,
            error_message="Workflow execution failed",
        )

        mock_executor = AsyncMock(spec=WorkflowExecutor)
        mock_executor.get_workflow_type = MagicMock(return_value="stock")
        mock_executor.validate = AsyncMock(return_value=True)
        mock_executor.execute = AsyncMock(side_effect=Exception("Workflow execution failed"))

        mock_research_repo.get_by_id = AsyncMock(return_value=research)
        mock_research_repo.save = AsyncMock(side_effect=[research, failed_research])

        use_case = ExecuteResearchUseCase(
            research_repository=mock_research_repo,
            profile_repository=None,
            workflow_executors=[mock_executor],
        )
        request = ExecuteResearchRequest(research_id=research_id, context={})
        response = await use_case.execute(request)

        assert isinstance(response, ExecuteResearchResponse)
        assert response.success is False
        assert response.research.status == ResearchStatus.FAILED
        assert response.research.error_message == "Workflow execution failed"
        assert mock_research_repo.save.call_count == 2  # Once for IN_PROGRESS, once for FAILED

    @pytest.mark.asyncio
    async def test_execute_with_multiple_executors(self) -> None:
        """Test execute with multiple executors, finding the correct one."""
        mock_research_repo = AsyncMock(spec=ResearchRepository)
        research_id = uuid4()
        research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="agent",
        )
        updated_research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="agent",
            status=ResearchStatus.COMPLETED,
            results={"result": "data"},
        )

        mock_static_executor = AsyncMock(spec=WorkflowExecutor)
        mock_static_executor.get_workflow_type = MagicMock(return_value="stock")
        mock_static_executor.validate = AsyncMock(return_value=False)

        mock_agentic_executor = AsyncMock(spec=WorkflowExecutor)
        mock_agentic_executor.get_workflow_type = MagicMock(return_value="agent")
        mock_agentic_executor.validate = AsyncMock(return_value=True)
        mock_agentic_executor.execute = AsyncMock(return_value={"result": "data"})

        mock_research_repo.get_by_id = AsyncMock(return_value=research)
        mock_research_repo.save = AsyncMock(side_effect=[research, updated_research])

        use_case = ExecuteResearchUseCase(
            research_repository=mock_research_repo,
            profile_repository=None,
            workflow_executors=[mock_static_executor, mock_agentic_executor],
        )
        request = ExecuteResearchRequest(research_id=research_id, context={})
        response = await use_case.execute(request)

        assert response.success is True
        assert response.research.status == ResearchStatus.COMPLETED
        # Static executor's validate should not be called because workflow_type doesn't match
        mock_static_executor.validate.assert_not_called()
        # Agentic executor's validate should be called because workflow_type matches
        mock_agentic_executor.validate.assert_called_once()
        mock_agentic_executor.execute.assert_called_once()
        mock_static_executor.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_with_profile_no_display_name(self) -> None:
        """Test execute with profile that has no display_name."""
        mock_research_repo = AsyncMock(spec=ResearchRepository)
        mock_profile_repo = AsyncMock(spec=ResearchProfileRepository)
        research_id = uuid4()
        profile_id = uuid4()

        research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            profile_id=profile_id,
        )
        profile = ResearchProfile(
            id=profile_id,
            financial_literacy=FinancialLiteracy.BEGINNER,
            preferences={},
            display_name=None,
        )
        updated_research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            profile_id=profile_id,
            status=ResearchStatus.COMPLETED,
            results={"result": "data"},
        )

        mock_executor = AsyncMock(spec=WorkflowExecutor)
        mock_executor.get_workflow_type = MagicMock(return_value="stock")
        mock_executor.validate = AsyncMock(return_value=True)
        mock_executor.execute = AsyncMock(return_value={"result": "data"})

        mock_research_repo.get_by_id = AsyncMock(return_value=research)
        mock_profile_repo.get_by_id = AsyncMock(return_value=profile)
        mock_research_repo.save = AsyncMock(side_effect=[research, updated_research])

        use_case = ExecuteResearchUseCase(
            research_repository=mock_research_repo,
            workflow_executors=[mock_executor],
            profile_repository=mock_profile_repo,
        )
        request = ExecuteResearchRequest(research_id=research_id, context={})
        response = await use_case.execute(request)

        assert response.success is True
        call_args = mock_executor.execute.call_args
        execution_context = call_args[0][1]
        assert execution_context["financial_literacy"] == "beginner"
        assert execution_context["profile_preferences"] == {}
        assert "profile_display_name" not in execution_context
