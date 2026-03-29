"""Unit tests for profile CLI commands."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from copinance_os.domain.models.profile import AnalysisProfile, FinancialLiteracy
from copinance_os.interfaces.cli.commands.profile import (
    create_profile,
    delete_profile,
    get_current_profile,
    get_profile,
    list_profiles,
    set_current_profile,
)
from copinance_os.research.workflows.profile import (
    CreateProfileResponse,
    DeleteProfileResponse,
    GetCurrentProfileResponse,
    GetProfileResponse,
    ListProfilesResponse,
    SetCurrentProfileResponse,
)


@pytest.mark.unit
class TestProfileCLI:
    """Test profile-related CLI commands."""

    @patch("copinance_os.interfaces.cli.commands.profile.get_container")
    @patch("copinance_os.interfaces.cli.commands.profile.console")
    def test_create_profile(self, mock_console: MagicMock, mock_get_container: MagicMock) -> None:
        """Test create profile command."""
        # Setup mocks
        profile_id = uuid4()
        mock_profile = AnalysisProfile(
            id=profile_id,
            financial_literacy=FinancialLiteracy.INTERMEDIATE,
            display_name="Test Profile",
        )
        mock_response = CreateProfileResponse(profile=mock_profile)
        mock_use_case = AsyncMock()
        mock_use_case.execute = AsyncMock(return_value=mock_response)
        mock_get_container.return_value.create_profile_use_case.return_value = mock_use_case
        # Execute
        create_profile(literacy=FinancialLiteracy.INTERMEDIATE, name="Test Profile")

        # Verify
        mock_get_container.return_value.create_profile_use_case.assert_called_once()
        mock_use_case.execute.assert_called_once()
        call_args = mock_use_case.execute.call_args[0][0]
        assert call_args.financial_literacy == FinancialLiteracy.INTERMEDIATE
        assert call_args.display_name == "Test Profile"

        # Verify console output
        assert mock_console.print.called
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("Profile created successfully" in str(call) for call in print_calls)
        assert any(str(profile_id) in str(call) for call in print_calls)

    @patch("copinance_os.interfaces.cli.commands.profile.get_container")
    @patch("copinance_os.interfaces.cli.commands.profile.console")
    def test_list_profiles_with_results(
        self,
        mock_console: MagicMock,
        mock_get_container: MagicMock,
    ) -> None:
        """Test list profiles command with results."""

        # Setup mocks
        profile_id1 = uuid4()
        profile_id2 = uuid4()

        mock_profile1 = AnalysisProfile(
            id=profile_id1,
            financial_literacy=FinancialLiteracy.BEGINNER,
            display_name="Profile 1",
        )
        mock_profile2 = AnalysisProfile(
            id=profile_id2,
            financial_literacy=FinancialLiteracy.ADVANCED,
            display_name="Profile 2",
        )

        mock_list_response = ListProfilesResponse(profiles=[mock_profile1, mock_profile2])
        mock_current_response = GetCurrentProfileResponse(profile=mock_profile1)

        mock_list_use_case = AsyncMock()
        mock_list_use_case.execute = AsyncMock(return_value=mock_list_response)
        mock_get_container.return_value.list_profiles_use_case.return_value = mock_list_use_case

        mock_current_use_case = AsyncMock()
        mock_current_use_case.execute = AsyncMock(return_value=mock_current_response)
        mock_get_container.return_value.get_current_profile_use_case.return_value = (
            mock_current_use_case
        )
        # Execute
        list_profiles(limit=100)

        # Verify
        mock_list_use_case.execute.assert_called_once()
        mock_current_use_case.execute.assert_called_once()

        # Verify table was printed (not "No profiles found")
        assert mock_console.print.called
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert not any("No profiles found" in str(call) for call in print_calls)

    @patch("copinance_os.interfaces.cli.commands.profile.get_container")
    @patch("copinance_os.interfaces.cli.commands.profile.console")
    def test_list_profiles_no_results(
        self,
        mock_console: MagicMock,
        mock_get_container: MagicMock,
    ) -> None:
        """Test list profiles command with no results."""

        # Setup mocks
        mock_list_response = ListProfilesResponse(profiles=[])
        mock_current_response = GetCurrentProfileResponse(profile=None)

        mock_list_use_case = AsyncMock()
        mock_list_use_case.execute = AsyncMock(return_value=mock_list_response)
        mock_get_container.return_value.list_profiles_use_case.return_value = mock_list_use_case

        mock_current_use_case = AsyncMock()
        mock_current_use_case.execute = AsyncMock(return_value=mock_current_response)
        mock_get_container.return_value.get_current_profile_use_case.return_value = (
            mock_current_use_case
        )
        # Execute
        list_profiles(limit=100)

        # Verify "No profiles found" was printed
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("No profiles found" in str(call) for call in print_calls)

    @patch("copinance_os.interfaces.cli.commands.profile.get_container")
    @patch("copinance_os.interfaces.cli.commands.profile.console")
    def test_get_profile_found(
        self, mock_console: MagicMock, mock_get_container: MagicMock
    ) -> None:
        """Test get profile command when profile is found."""

        # Setup mocks
        profile_id = uuid4()
        mock_profile = AnalysisProfile(
            id=profile_id,
            financial_literacy=FinancialLiteracy.INTERMEDIATE,
            display_name="Test Profile",
            preferences={"key1": "value1"},
        )
        mock_response = GetProfileResponse(profile=mock_profile)
        mock_use_case = AsyncMock()
        mock_use_case.execute = AsyncMock(return_value=mock_response)
        mock_get_container.return_value.get_profile_use_case.return_value = mock_use_case
        # Execute
        get_profile(profile_id=profile_id)

        # Verify
        mock_use_case.execute.assert_called_once()
        call_args = mock_use_case.execute.call_args[0][0]
        assert call_args.profile_id == profile_id

        # Verify console output
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert not any("Profile not found" in str(call) for call in print_calls)
        assert any("Profile Details" in str(call) for call in print_calls)

    @patch("copinance_os.interfaces.cli.commands.profile.get_container")
    @patch("copinance_os.interfaces.cli.commands.profile.console")
    def test_get_profile_not_found(
        self, mock_console: MagicMock, mock_get_container: MagicMock
    ) -> None:
        """Test get profile command when profile is not found."""

        # Setup mocks
        profile_id = uuid4()
        mock_response = GetProfileResponse(profile=None)
        mock_use_case = AsyncMock()
        mock_use_case.execute = AsyncMock(return_value=mock_response)
        mock_get_container.return_value.get_profile_use_case.return_value = mock_use_case
        # Execute
        get_profile(profile_id=profile_id)

        # Verify "Profile not found" was printed
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("Profile not found" in str(call) for call in print_calls)

    @patch("copinance_os.interfaces.cli.commands.profile.get_container")
    @patch("copinance_os.interfaces.cli.commands.profile.console")
    def test_get_current_profile_set(
        self, mock_console: MagicMock, mock_get_container: MagicMock
    ) -> None:
        """Test get current profile command when current profile is set."""

        # Setup mocks
        profile_id = uuid4()
        mock_profile = AnalysisProfile(
            id=profile_id,
            financial_literacy=FinancialLiteracy.ADVANCED,
            display_name="Current Profile",
        )
        mock_response = GetCurrentProfileResponse(profile=mock_profile)
        mock_use_case = AsyncMock()
        mock_use_case.execute = AsyncMock(return_value=mock_response)
        mock_get_container.return_value.get_current_profile_use_case.return_value = mock_use_case
        # Execute
        get_current_profile()

        # Verify
        mock_use_case.execute.assert_called_once()

        # Verify console output
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert not any("No current profile set" in str(call) for call in print_calls)
        assert any("Current Profile" in str(call) for call in print_calls)

    @patch("copinance_os.interfaces.cli.commands.profile.get_container")
    @patch("copinance_os.interfaces.cli.commands.profile.console")
    def test_get_current_profile_not_set(
        self, mock_console: MagicMock, mock_get_container: MagicMock
    ) -> None:
        """Test get current profile command when no current profile is set."""

        # Setup mocks
        mock_response = GetCurrentProfileResponse(profile=None)
        mock_use_case = AsyncMock()
        mock_use_case.execute = AsyncMock(return_value=mock_response)
        mock_get_container.return_value.get_current_profile_use_case.return_value = mock_use_case
        # Execute
        get_current_profile()

        # Verify "No current profile set" was printed
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("No current profile set" in str(call) for call in print_calls)

    @patch("copinance_os.interfaces.cli.commands.profile.get_container")
    @patch("copinance_os.interfaces.cli.commands.profile.console")
    def test_set_current_profile(
        self, mock_console: MagicMock, mock_get_container: MagicMock
    ) -> None:
        """Test set current profile command."""

        # Setup mocks
        profile_id = uuid4()
        mock_profile = AnalysisProfile(
            id=profile_id,
            financial_literacy=FinancialLiteracy.BEGINNER,
            display_name="Test Profile",
        )
        mock_response = SetCurrentProfileResponse(profile=mock_profile)
        mock_use_case = AsyncMock()
        mock_use_case.execute = AsyncMock(return_value=mock_response)
        mock_get_container.return_value.set_current_profile_use_case.return_value = mock_use_case
        # Execute
        set_current_profile(profile_id=profile_id)

        # Verify
        mock_use_case.execute.assert_called_once()
        call_args = mock_use_case.execute.call_args[0][0]
        assert call_args.profile_id == profile_id

        # Verify success message
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("Current profile set" in str(call) for call in print_calls)

    @patch("copinance_os.interfaces.cli.commands.profile.get_container")
    @patch("copinance_os.interfaces.cli.commands.profile.console")
    def test_set_current_profile_clear(
        self, mock_console: MagicMock, mock_get_container: MagicMock
    ) -> None:
        """Test set current profile command to clear current profile."""

        # Setup mocks
        mock_response = SetCurrentProfileResponse(profile=None)
        mock_use_case = AsyncMock()
        mock_use_case.execute = AsyncMock(return_value=mock_response)
        mock_get_container.return_value.set_current_profile_use_case.return_value = mock_use_case
        # Execute with None to clear
        set_current_profile(profile_id=None)

        # Verify
        mock_use_case.execute.assert_called_once()
        call_args = mock_use_case.execute.call_args[0][0]
        assert call_args.profile_id is None

        # Verify clear message
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("Current profile cleared" in str(call) for call in print_calls)

    @patch("copinance_os.interfaces.cli.commands.profile.get_container")
    @patch("copinance_os.interfaces.cli.commands.profile.console")
    def test_set_current_profile_error(
        self, mock_console: MagicMock, mock_get_container: MagicMock
    ) -> None:
        """Test set current profile command with error."""

        # Setup mocks
        profile_id = uuid4()
        mock_use_case = AsyncMock()
        mock_use_case.execute = AsyncMock(side_effect=ValueError("Profile not found"))
        mock_get_container.return_value.set_current_profile_use_case.return_value = mock_use_case
        # Execute
        set_current_profile(profile_id=profile_id)

        # Verify error message
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("Error" in str(call) for call in print_calls)

    @patch("copinance_os.interfaces.cli.commands.profile.get_container")
    @patch("copinance_os.interfaces.cli.commands.profile.typer.confirm")
    @patch("copinance_os.interfaces.cli.commands.profile.console")
    def test_delete_profile_with_confirmation(
        self,
        mock_console: MagicMock,
        mock_confirm: MagicMock,
        mock_get_container: MagicMock,
    ) -> None:
        """Test delete profile command with confirmation."""

        # Setup mocks
        profile_id = uuid4()
        mock_profile = AnalysisProfile(
            id=profile_id,
            financial_literacy=FinancialLiteracy.BEGINNER,
            display_name="Test Profile",
        )

        mock_get_response = GetProfileResponse(profile=mock_profile)
        mock_use_case_provider = AsyncMock()
        mock_use_case_provider.execute = AsyncMock(return_value=mock_get_response)
        mock_get_container.return_value.get_profile_use_case.return_value = mock_use_case_provider

        mock_current_response = GetCurrentProfileResponse(profile=None)
        mock_current_use_case = AsyncMock()
        mock_current_use_case.execute = AsyncMock(return_value=mock_current_response)
        mock_get_container.return_value.get_current_profile_use_case.return_value = (
            mock_current_use_case
        )

        mock_delete_response = DeleteProfileResponse(success=True)
        mock_delete_use_case = AsyncMock()
        mock_delete_use_case.execute = AsyncMock(return_value=mock_delete_response)
        mock_get_container.return_value.delete_profile_use_case.return_value = mock_delete_use_case

        mock_confirm.return_value = True
        # Execute
        delete_profile(profile_id=profile_id, force=False)

        # Verify
        mock_get_container.return_value.get_profile_use_case.assert_called()
        mock_delete_use_case.execute.assert_called_once()
        mock_confirm.assert_called_once()

        # Verify success message
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("Profile deleted successfully" in str(call) for call in print_calls)

    @patch("copinance_os.interfaces.cli.commands.profile.get_container")
    @patch("copinance_os.interfaces.cli.commands.profile.console")
    def test_delete_profile_force(
        self,
        mock_console: MagicMock,
        mock_get_container: MagicMock,
    ) -> None:
        """Test delete profile command with force flag."""

        # Setup mocks
        profile_id = uuid4()
        mock_profile = AnalysisProfile(
            id=profile_id,
            financial_literacy=FinancialLiteracy.BEGINNER,
            display_name="Test Profile",
        )

        mock_get_response = GetProfileResponse(profile=mock_profile)
        mock_use_case_provider = AsyncMock()
        mock_use_case_provider.execute = AsyncMock(return_value=mock_get_response)
        mock_get_container.return_value.get_profile_use_case.return_value = mock_use_case_provider

        mock_current_response = GetCurrentProfileResponse(profile=None)
        mock_current_use_case = AsyncMock()
        mock_current_use_case.execute = AsyncMock(return_value=mock_current_response)
        mock_get_container.return_value.get_current_profile_use_case.return_value = (
            mock_current_use_case
        )

        mock_delete_response = DeleteProfileResponse(success=True)
        mock_delete_use_case = AsyncMock()
        mock_delete_use_case.execute = AsyncMock(return_value=mock_delete_response)
        mock_get_container.return_value.delete_profile_use_case.return_value = mock_delete_use_case
        # Execute with force=True (no confirmation needed)
        delete_profile(profile_id=profile_id, force=True)

        # Verify
        mock_delete_use_case.execute.assert_called_once()

        # Verify success message
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("Profile deleted successfully" in str(call) for call in print_calls)

    @patch("copinance_os.interfaces.cli.commands.profile.get_container")
    @patch("copinance_os.interfaces.cli.commands.profile.console")
    def test_delete_profile_not_found(
        self, mock_console: MagicMock, mock_get_container: MagicMock
    ) -> None:
        """Test delete profile command when profile is not found."""

        # Setup mocks
        profile_id = uuid4()
        mock_get_response = GetProfileResponse(profile=None)
        mock_use_case_provider = AsyncMock()
        mock_use_case_provider.execute = AsyncMock(return_value=mock_get_response)
        mock_get_container.return_value.get_profile_use_case.return_value = mock_use_case_provider
        # Execute
        delete_profile(profile_id=profile_id, force=True)

        # Verify "Profile not found" was printed
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("Profile not found" in str(call) for call in print_calls)
