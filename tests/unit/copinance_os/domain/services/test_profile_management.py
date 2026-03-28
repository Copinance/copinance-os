"""Unit tests for profile management domain service."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from copinance_os.domain.exceptions import ProfileNotFoundError
from copinance_os.domain.models.profile import AnalysisProfile, FinancialLiteracy
from copinance_os.domain.ports.repositories import AnalysisProfileRepository
from copinance_os.domain.services.profile_management import ProfileManagementService


@pytest.mark.unit
class TestProfileManagementService:
    """Test ProfileManagementService."""

    @pytest.fixture
    def mock_repository(self) -> AsyncMock:
        """Provide a mock profile repository."""
        return AsyncMock(spec=AnalysisProfileRepository)

    @pytest.fixture
    def service(self, mock_repository: AsyncMock) -> ProfileManagementService:
        """Provide a ProfileManagementService instance."""
        return ProfileManagementService(profile_repository=mock_repository)

    async def test_validate_profile_exists_success(
        self, service: ProfileManagementService, mock_repository: AsyncMock
    ) -> None:
        """Test validate_profile_exists when profile exists."""
        profile_id = uuid4()
        profile = AnalysisProfile(
            id=profile_id,
            financial_literacy=FinancialLiteracy.INTERMEDIATE,
            display_name="Test Profile",
        )
        mock_repository.get_by_id = AsyncMock(return_value=profile)

        result = await service.validate_profile_exists(profile_id)

        assert result == profile
        mock_repository.get_by_id.assert_called_once_with(profile_id)

    async def test_validate_profile_exists_not_found(
        self, service: ProfileManagementService, mock_repository: AsyncMock
    ) -> None:
        """Test validate_profile_exists when profile does not exist."""
        profile_id = uuid4()
        mock_repository.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(ProfileNotFoundError, match=str(profile_id)):
            await service.validate_profile_exists(profile_id)

        mock_repository.get_by_id.assert_called_once_with(profile_id)

    def test_should_auto_set_as_current(
        self, service: ProfileManagementService, mock_repository: AsyncMock
    ) -> None:
        """Test should_auto_set_as_current returns True for new profiles."""
        profile = AnalysisProfile(
            id=uuid4(),
            financial_literacy=FinancialLiteracy.INTERMEDIATE,
            display_name="Test Profile",
        )

        result = service.should_auto_set_as_current(profile)

        assert result is True

    def test_should_clear_current_on_delete_when_current(
        self, service: ProfileManagementService, mock_repository: AsyncMock
    ) -> None:
        """Test should_clear_current_on_delete when deleting current profile."""
        profile_id = uuid4()

        result = service.should_clear_current_on_delete(profile_id, current_profile_id=profile_id)

        assert result is True

    def test_should_clear_current_on_delete_when_not_current(
        self, service: ProfileManagementService, mock_repository: AsyncMock
    ) -> None:
        """Test should_clear_current_on_delete when deleting non-current profile."""
        profile_id = uuid4()
        other_profile_id = uuid4()

        result = service.should_clear_current_on_delete(
            profile_id, current_profile_id=other_profile_id
        )

        assert result is False

    def test_should_clear_current_on_delete_when_no_current(
        self, service: ProfileManagementService, mock_repository: AsyncMock
    ) -> None:
        """Test should_clear_current_on_delete when no current profile."""
        profile_id = uuid4()

        result = service.should_clear_current_on_delete(profile_id, current_profile_id=None)

        assert result is False
