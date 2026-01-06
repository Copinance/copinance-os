"""Unit tests for research CLI commands."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from copinanceos.application.use_cases.profile import GetCurrentProfileResponse
from copinanceos.application.use_cases.research import (
    CreateResearchResponse,
    ExecuteResearchResponse,
    GetResearchResponse,
    SetResearchContextResponse,
)
from copinanceos.cli.research import (
    WorkflowType,
    create_research,
    execute_research,
    get_research,
    run_research,
    set_research_context,
)
from copinanceos.domain.exceptions import ResearchNotFoundError
from copinanceos.domain.models.research import Research, ResearchStatus, ResearchTimeframe


@pytest.mark.unit
class TestResearchCLI:
    """Test research-related CLI commands."""

    @patch("copinanceos.cli.research.typer.confirm")
    @patch("copinanceos.cli.research.container.create_research_use_case")
    @patch("copinanceos.cli.research.container.get_current_profile_use_case")
    @patch("copinanceos.cli.research.console")
    def test_create_research_without_profile(
        self,
        mock_console: MagicMock,
        mock_current_provider: MagicMock,
        mock_create_provider: MagicMock,
        mock_confirm: MagicMock,
    ) -> None:
        """Test create research command without profile."""

        # Setup mocks
        research_id = uuid4()
        mock_research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
        )
        mock_create_response = CreateResearchResponse(research=mock_research)
        mock_create_use_case = AsyncMock()
        mock_create_use_case.execute = AsyncMock(return_value=mock_create_response)
        mock_create_provider.return_value = mock_create_use_case

        mock_current_response = GetCurrentProfileResponse(profile=None)
        mock_current_use_case = AsyncMock()
        mock_current_use_case.execute = AsyncMock(return_value=mock_current_response)
        mock_current_provider.return_value = mock_current_use_case

        # Mock typer.confirm to return False (user declines to create profile)
        mock_confirm.return_value = False

        # Execute
        create_research(
            symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow=WorkflowType.STOCK,
            profile_id=None,
        )

        # Verify
        mock_create_use_case.execute.assert_called_once()
        call_args = mock_create_use_case.execute.call_args[0][0]
        assert call_args.stock_symbol == "AAPL"
        assert call_args.timeframe == ResearchTimeframe.MID_TERM
        assert call_args.workflow_type == "stock"
        assert call_args.profile_id is None

        # Verify console output
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("Research created successfully" in str(call) for call in print_calls)

    @patch("copinanceos.cli.research.container.create_research_use_case")
    @patch("copinanceos.cli.research.container.get_current_profile_use_case")
    @patch("copinanceos.cli.research.console")
    def test_create_research_with_current_profile(
        self,
        mock_console: MagicMock,
        mock_current_provider: MagicMock,
        mock_create_provider: MagicMock,
    ) -> None:
        """Test create research command with current profile."""

        # Setup mocks
        from copinanceos.domain.models.research_profile import ResearchProfile  # noqa: PLC0415

        profile_id = uuid4()
        research_id = uuid4()
        mock_profile = ResearchProfile(id=profile_id, financial_literacy="beginner")
        mock_research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            profile_id=profile_id,
        )

        mock_create_response = CreateResearchResponse(research=mock_research)
        mock_create_use_case = AsyncMock()
        mock_create_use_case.execute = AsyncMock(return_value=mock_create_response)
        mock_create_provider.return_value = mock_create_use_case

        mock_current_response = GetCurrentProfileResponse(profile=mock_profile)
        mock_current_use_case = AsyncMock()
        mock_current_use_case.execute = AsyncMock(return_value=mock_current_response)
        mock_current_provider.return_value = mock_current_use_case
        # Execute without explicit profile_id (should use current)
        create_research(
            symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow=WorkflowType.STOCK,
            profile_id=None,
        )

        # Verify profile_id was set from current profile
        call_args = mock_create_use_case.execute.call_args[0][0]
        assert call_args.profile_id == profile_id

    @patch("copinanceos.cli.research.typer.confirm")
    @patch("copinanceos.cli.research.container.create_research_use_case")
    @patch("copinanceos.cli.research.container.execute_research_use_case")
    @patch("copinanceos.cli.research.container.get_current_profile_use_case")
    @patch("copinanceos.cli.research.console")
    def test_run_research_success(
        self,
        mock_console: MagicMock,
        mock_current_provider: MagicMock,
        mock_execute_provider: MagicMock,
        mock_create_provider: MagicMock,
        mock_confirm: MagicMock,
    ) -> None:
        """Test run research command (create and execute)."""

        # Setup mocks
        research_id = uuid4()
        mock_research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            status=ResearchStatus.COMPLETED,
            results={"key1": "value1", "key2": "value2"},
        )

        mock_create_response = CreateResearchResponse(research=mock_research)
        mock_create_use_case = AsyncMock()
        mock_create_use_case.execute = AsyncMock(return_value=mock_create_response)
        mock_create_provider.return_value = mock_create_use_case

        mock_execute_response = ExecuteResearchResponse(research=mock_research, success=True)
        mock_execute_use_case = AsyncMock()
        mock_execute_use_case.execute = AsyncMock(return_value=mock_execute_response)
        mock_execute_provider.return_value = mock_execute_use_case

        mock_current_response = GetCurrentProfileResponse(profile=None)
        mock_current_use_case = AsyncMock()
        mock_current_use_case.execute = AsyncMock(return_value=mock_current_response)
        mock_current_provider.return_value = mock_current_use_case

        # Mock typer.confirm to return False (user declines to create profile)
        mock_confirm.return_value = False

        # Execute
        run_research(
            symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow=WorkflowType.STOCK,
            profile_id=None,
        )

        # Verify both create and execute were called
        mock_create_use_case.execute.assert_called_once()
        mock_execute_use_case.execute.assert_called_once()

        # Verify success message
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("Research executed successfully" in str(call) for call in print_calls)
        assert any("Results:" in str(call) for call in print_calls)

    @patch("copinanceos.cli.research.typer.confirm")
    @patch("copinanceos.cli.research.container.create_research_use_case")
    @patch("copinanceos.cli.research.container.execute_research_use_case")
    @patch("copinanceos.cli.research.container.get_current_profile_use_case")
    @patch("copinanceos.cli.research.console")
    def test_run_research_failure(
        self,
        mock_console: MagicMock,
        mock_current_provider: MagicMock,
        mock_execute_provider: MagicMock,
        mock_create_provider: MagicMock,
        mock_confirm: MagicMock,
    ) -> None:
        """Test run research command with execution failure."""

        # Setup mocks
        research_id = uuid4()
        mock_research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            status=ResearchStatus.FAILED,
            error_message="Execution failed",
        )

        mock_create_response = CreateResearchResponse(research=mock_research)
        mock_create_use_case = AsyncMock()
        mock_create_use_case.execute = AsyncMock(return_value=mock_create_response)
        mock_create_provider.return_value = mock_create_use_case

        mock_execute_response = ExecuteResearchResponse(research=mock_research, success=False)
        mock_execute_use_case = AsyncMock()
        mock_execute_use_case.execute = AsyncMock(return_value=mock_execute_response)
        mock_execute_provider.return_value = mock_execute_use_case

        mock_current_response = GetCurrentProfileResponse(profile=None)
        mock_current_use_case = AsyncMock()
        mock_current_use_case.execute = AsyncMock(return_value=mock_current_response)
        mock_current_provider.return_value = mock_current_use_case

        # Mock typer.confirm to return False (user declines to create profile)
        mock_confirm.return_value = False

        # Execute
        run_research(
            symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow=WorkflowType.STOCK,
            profile_id=None,
        )

        # Verify failure message
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("Research execution failed" in str(call) for call in print_calls)
        assert any("Error:" in str(call) for call in print_calls)

    @patch("copinanceos.cli.research.container.execute_research_use_case")
    @patch("copinanceos.cli.research.container.get_research_use_case")
    @patch("copinanceos.cli.research.console")
    def test_execute_research_success(
        self,
        mock_console: MagicMock,
        mock_get_research_provider: MagicMock,
        mock_execute_provider: MagicMock,
    ) -> None:
        """Test execute research command with success."""

        # Setup mocks
        research_id = uuid4()
        profile_id = uuid4()
        mock_research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            status=ResearchStatus.COMPLETED,
            results={"result": "success"},
            profile_id=profile_id,  # Research has a profile, so no prompting needed
        )

        # Mock get_research_use_case (called to check if research has profile)
        mock_get_response = GetResearchResponse(research=mock_research)
        mock_get_use_case = AsyncMock()
        mock_get_use_case.execute = AsyncMock(return_value=mock_get_response)
        mock_get_research_provider.return_value = mock_get_use_case

        # Mock execute_research_use_case
        mock_execute_response = ExecuteResearchResponse(research=mock_research, success=True)
        mock_execute_use_case = AsyncMock()
        mock_execute_use_case.execute = AsyncMock(return_value=mock_execute_response)
        mock_execute_provider.return_value = mock_execute_use_case

        # Execute
        execute_research(research_id=research_id)

        # Verify get_research was called to check profile
        mock_get_use_case.execute.assert_called_once()
        # Verify execute was called
        mock_execute_use_case.execute.assert_called_once()
        call_args = mock_execute_use_case.execute.call_args[0][0]
        assert call_args.research_id == research_id

        # Verify success message
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("Research executed successfully" in str(call) for call in print_calls)

    @patch("copinanceos.cli.research.typer.confirm")
    @patch("copinanceos.cli.research.container.get_current_profile_use_case")
    @patch("copinanceos.cli.research.container.set_research_context_use_case")
    @patch("copinanceos.cli.research.container.execute_research_use_case")
    @patch("copinanceos.cli.research.container.get_research_use_case")
    @patch("copinanceos.cli.research.console")
    def test_execute_research_failure(
        self,
        mock_console: MagicMock,
        mock_get_research_provider: MagicMock,
        mock_execute_provider: MagicMock,
        mock_set_context_provider: MagicMock,
        mock_current_profile_provider: MagicMock,
        mock_confirm: MagicMock,
    ) -> None:
        """Test execute research command with failure."""

        # Setup mocks
        research_id = uuid4()
        mock_research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            status=ResearchStatus.FAILED,
            error_message="Test error",
            profile_id=None,  # No profile, will prompt but user declines
        )

        # Mock get_research_use_case (called to check if research has profile)
        mock_get_response = GetResearchResponse(research=mock_research)
        mock_get_use_case = AsyncMock()
        mock_get_use_case.execute = AsyncMock(return_value=mock_get_response)
        mock_get_research_provider.return_value = mock_get_use_case

        # Mock get_current_profile_use_case (called by _ensure_profile_with_literacy)
        mock_current_response = GetCurrentProfileResponse(profile=None)
        mock_current_use_case = AsyncMock()
        mock_current_use_case.execute = AsyncMock(return_value=mock_current_response)
        mock_current_profile_provider.return_value = mock_current_use_case

        # Mock execute_research_use_case
        mock_execute_response = ExecuteResearchResponse(research=mock_research, success=False)
        mock_execute_use_case = AsyncMock()
        mock_execute_use_case.execute = AsyncMock(return_value=mock_execute_response)
        mock_execute_provider.return_value = mock_execute_use_case

        # Mock typer.confirm to return False (user declines to create profile)
        mock_confirm.return_value = False

        # Execute
        execute_research(research_id=research_id)

        # Verify failure message
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("Research execution failed" in str(call) for call in print_calls)

    @patch("copinanceos.cli.research.container.get_research_use_case")
    @patch("copinanceos.cli.research.console")
    def test_get_research_found(
        self, mock_console: MagicMock, mock_use_case_provider: MagicMock
    ) -> None:
        """Test get research command when research is found."""

        # Setup mocks
        research_id = uuid4()
        mock_research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            status=ResearchStatus.COMPLETED,
            results={"key": "value"},
        )

        mock_response = GetResearchResponse(research=mock_research)
        mock_use_case = AsyncMock()
        mock_use_case.execute = AsyncMock(return_value=mock_response)
        mock_use_case_provider.return_value = mock_use_case
        # Execute
        get_research(research_id=research_id)

        # Verify
        mock_use_case.execute.assert_called_once()
        call_args = mock_use_case.execute.call_args[0][0]
        assert call_args.research_id == research_id

        # Verify console output
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert not any("Research not found" in str(call) for call in print_calls)
        assert any("Research Details" in str(call) for call in print_calls)

    @patch("copinanceos.cli.research.container.get_research_use_case")
    @patch("copinanceos.cli.research.console")
    def test_get_research_not_found(
        self, mock_console: MagicMock, mock_use_case_provider: MagicMock
    ) -> None:
        """Test get research command when research is not found."""

        # Setup mocks
        research_id = uuid4()
        mock_response = GetResearchResponse(research=None)
        mock_use_case = AsyncMock()
        mock_use_case.execute = AsyncMock(return_value=mock_response)
        mock_use_case_provider.return_value = mock_use_case
        # Execute
        get_research(research_id=research_id)

        # Verify "Research not found" was printed
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("Research not found" in str(call) for call in print_calls)

    @patch("copinanceos.cli.research.container.set_research_context_use_case")
    @patch("copinanceos.cli.research.console")
    def test_set_research_context(
        self, mock_console: MagicMock, mock_use_case_provider: MagicMock
    ) -> None:
        """Test set research context command."""

        # Setup mocks
        research_id = uuid4()
        profile_id = uuid4()
        mock_research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            profile_id=profile_id,
        )

        mock_response = SetResearchContextResponse(research=mock_research)
        mock_use_case = AsyncMock()
        mock_use_case.execute = AsyncMock(return_value=mock_response)
        mock_use_case_provider.return_value = mock_use_case
        # Execute
        set_research_context(research_id=research_id, profile_id=profile_id)

        # Verify
        mock_use_case.execute.assert_called_once()
        call_args = mock_use_case.execute.call_args[0][0]
        assert call_args.research_id == research_id
        assert call_args.profile_id == profile_id

        # Verify success message
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("Research context set successfully" in str(call) for call in print_calls)

    @patch("copinanceos.cli.research.container.set_research_context_use_case")
    @patch("copinanceos.cli.research.console")
    def test_set_research_context_clear(
        self, mock_console: MagicMock, mock_use_case_provider: MagicMock
    ) -> None:
        """Test set research context command to clear context."""

        # Setup mocks
        research_id = uuid4()
        mock_research = Research(
            id=research_id,
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            profile_id=None,
        )

        mock_response = SetResearchContextResponse(research=mock_research)
        mock_use_case = AsyncMock()
        mock_use_case.execute = AsyncMock(return_value=mock_response)
        mock_use_case_provider.return_value = mock_use_case
        # Execute with None to clear
        set_research_context(research_id=research_id, profile_id=None)

        # Verify
        call_args = mock_use_case.execute.call_args[0][0]
        assert call_args.profile_id is None

        # Verify clear message
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("Research context cleared" in str(call) for call in print_calls)

    @patch("copinanceos.cli.research.container.set_research_context_use_case")
    @patch("copinanceos.cli.error_handler.console")
    @patch("copinanceos.cli.research.console")
    def test_set_research_context_error(
        self,
        mock_console: MagicMock,
        mock_error_console: MagicMock,
        mock_use_case_provider: MagicMock,
    ) -> None:
        """Test set research context command with error."""

        # Setup mocks
        research_id = uuid4()
        profile_id = uuid4()
        mock_use_case = AsyncMock()
        mock_use_case.execute = AsyncMock(side_effect=ResearchNotFoundError("Research not found"))
        mock_use_case_provider.return_value = mock_use_case
        # Execute
        set_research_context(research_id=research_id, profile_id=profile_id)

        # Verify error was handled (error handler console.print was called)
        assert mock_error_console.print.called
        # Verify the use case was called
        mock_use_case.execute.assert_called_once()
