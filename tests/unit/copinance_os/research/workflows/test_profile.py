"""Unit tests for profile use cases."""

import tempfile
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

from copinance_os.data.repositories.profile.current_profile import CurrentProfile
from copinance_os.domain.exceptions import ProfileNotFoundError
from copinance_os.domain.models.profile import AnalysisProfile, FinancialLiteracy
from copinance_os.domain.ports.repositories import AnalysisProfileRepository
from copinance_os.domain.services.profile_management import ProfileManagementService
from copinance_os.research.workflows.profile import (
    CreateProfileRequest,
    CreateProfileUseCase,
    DeleteProfileRequest,
    DeleteProfileUseCase,
    GetCurrentProfileRequest,
    GetCurrentProfileUseCase,
    GetProfileRequest,
    GetProfileUseCase,
    ListProfilesRequest,
    ListProfilesUseCase,
    SetCurrentProfileRequest,
    SetCurrentProfileUseCase,
)


@pytest.fixture
def temp_profile_config_path() -> Path:
    """Provide a temporary directory for profile config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def config_file_path(temp_profile_config_path: Path) -> Path:
    """Provide a config file path in temp directory."""
    path = temp_profile_config_path / "state" / "v2" / "app.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture
def current_profile(config_file_path: Path) -> CurrentProfile:
    """Provide a CurrentProfile instance with isolated storage."""
    # Mock the config path to use temp directory
    with patch(
        "copinance_os.data.repositories.profile.current_profile._get_config_path"
    ) as mock_path:
        mock_path.return_value = config_file_path
        yield CurrentProfile()


@pytest.fixture
def profile_service(
    profile_repository: AnalysisProfileRepository,
) -> ProfileManagementService:
    """Provide a ProfileManagementService instance."""
    return ProfileManagementService(profile_repository)


@pytest.mark.unit
class TestProfileUseCases:
    """Test profile-related use cases."""

    @pytest.mark.asyncio
    async def test_create_profile_use_case(
        self,
        profile_repository: AnalysisProfileRepository,
        profile_service: ProfileManagementService,
        current_profile: CurrentProfile,
    ) -> None:
        """Test creating a profile through use case."""
        use_case = CreateProfileUseCase(profile_repository, profile_service, current_profile)
        request = CreateProfileRequest(
            financial_literacy=FinancialLiteracy.INTERMEDIATE,
            display_name="Test Investor",
            preferences={"theme": "tech"},
        )

        response = await use_case.execute(request)

        assert response.profile.financial_literacy == FinancialLiteracy.INTERMEDIATE
        assert response.profile.display_name == "Test Investor"
        assert response.profile.preferences == {"theme": "tech"}
        # Verify profile is automatically set as current
        assert current_profile.get_current_profile_id() == response.profile.id

    @pytest.mark.asyncio
    async def test_create_profile_with_defaults(
        self,
        profile_repository: AnalysisProfileRepository,
        profile_service: ProfileManagementService,
        current_profile: CurrentProfile,
    ) -> None:
        """Test creating a profile with default values."""
        use_case = CreateProfileUseCase(profile_repository, profile_service, current_profile)
        request = CreateProfileRequest()

        response = await use_case.execute(request)

        assert response.profile.financial_literacy == FinancialLiteracy.INTERMEDIATE
        assert response.profile.display_name is None
        assert response.profile.preferences == {}

    @pytest.mark.asyncio
    async def test_get_profile_use_case(
        self,
        profile_repository: AnalysisProfileRepository,
    ) -> None:
        """Test getting a profile by ID through use case."""
        # Create a profile first
        profile = AnalysisProfile(
            financial_literacy=FinancialLiteracy.ADVANCED,
            display_name="Advanced Investor",
        )
        saved_profile = await profile_repository.save(profile)

        use_case = GetProfileUseCase(profile_repository)
        request = GetProfileRequest(profile_id=saved_profile.id)

        response = await use_case.execute(request)

        assert response.profile is not None
        assert response.profile.id == saved_profile.id
        assert response.profile.financial_literacy == FinancialLiteracy.ADVANCED

    @pytest.mark.asyncio
    async def test_get_profile_not_found(
        self,
        profile_repository: AnalysisProfileRepository,
    ) -> None:
        """Test getting a non-existent profile."""
        use_case = GetProfileUseCase(profile_repository)
        request = GetProfileRequest(profile_id=uuid4())

        response = await use_case.execute(request)

        assert response.profile is None

    @pytest.mark.asyncio
    async def test_list_profiles_use_case(
        self,
        profile_repository: AnalysisProfileRepository,
    ) -> None:
        """Test listing profiles through use case."""
        # Create multiple profiles
        for i in range(5):
            profile = AnalysisProfile(
                financial_literacy=FinancialLiteracy.BEGINNER,
                display_name=f"Profile {i}",
            )
            await profile_repository.save(profile)

        use_case = ListProfilesUseCase(profile_repository)
        request = ListProfilesRequest(limit=10, offset=0)

        response = await use_case.execute(request)

        assert len(response.profiles) == 5
        assert all(isinstance(p, AnalysisProfile) for p in response.profiles)

    @pytest.mark.asyncio
    async def test_list_profiles_with_pagination(
        self,
        profile_repository: AnalysisProfileRepository,
    ) -> None:
        """Test listing profiles with pagination."""
        # Create multiple profiles
        for i in range(10):
            profile = AnalysisProfile(
                financial_literacy=FinancialLiteracy.BEGINNER,
                display_name=f"Profile {i}",
            )
            await profile_repository.save(profile)

        use_case = ListProfilesUseCase(profile_repository)
        request = ListProfilesRequest(limit=3, offset=0)

        response = await use_case.execute(request)

        assert len(response.profiles) == 3

    @pytest.mark.asyncio
    async def test_get_current_profile_use_case(
        self,
        profile_repository: AnalysisProfileRepository,
        current_profile: CurrentProfile,
    ) -> None:
        """Test getting the current profile through use case."""
        # Create and set a profile as current
        profile = AnalysisProfile(
            financial_literacy=FinancialLiteracy.INTERMEDIATE,
            display_name="Current Profile",
        )
        saved_profile = await profile_repository.save(profile)
        current_profile.set_current_profile_id(saved_profile.id)

        use_case = GetCurrentProfileUseCase(profile_repository, current_profile)
        request = GetCurrentProfileRequest()

        response = await use_case.execute(request)

        assert response.profile is not None
        assert response.profile.id == saved_profile.id
        assert response.profile.display_name == "Current Profile"

    @pytest.mark.asyncio
    async def test_get_current_profile_when_none_set(
        self,
        profile_repository: AnalysisProfileRepository,
        current_profile: CurrentProfile,
    ) -> None:
        """Test getting current profile when none is set."""
        use_case = GetCurrentProfileUseCase(profile_repository, current_profile)
        request = GetCurrentProfileRequest()

        response = await use_case.execute(request)

        assert response.profile is None

    @pytest.mark.asyncio
    async def test_set_current_profile_use_case(
        self,
        profile_repository: AnalysisProfileRepository,
        profile_service: ProfileManagementService,
        current_profile: CurrentProfile,
    ) -> None:
        """Test setting the current profile through use case."""
        # Create a profile
        profile = AnalysisProfile(
            financial_literacy=FinancialLiteracy.ADVANCED,
            display_name="New Current Profile",
        )
        saved_profile = await profile_repository.save(profile)

        use_case = SetCurrentProfileUseCase(profile_repository, profile_service, current_profile)
        request = SetCurrentProfileRequest(profile_id=saved_profile.id)

        response = await use_case.execute(request)

        assert response.profile is not None
        assert response.profile.id == saved_profile.id
        assert current_profile.get_current_profile_id() == saved_profile.id

    @pytest.mark.asyncio
    async def test_set_current_profile_invalid_id(
        self,
        profile_repository: AnalysisProfileRepository,
        profile_service: ProfileManagementService,
        current_profile: CurrentProfile,
    ) -> None:
        """Test setting current profile with invalid ID raises error."""
        use_case = SetCurrentProfileUseCase(profile_repository, profile_service, current_profile)
        request = SetCurrentProfileRequest(profile_id=uuid4())

        with pytest.raises(ProfileNotFoundError):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_clear_current_profile_use_case(
        self,
        profile_repository: AnalysisProfileRepository,
        profile_service: ProfileManagementService,
        current_profile: CurrentProfile,
    ) -> None:
        """Test clearing the current profile through use case."""
        # Set a profile as current first
        profile = AnalysisProfile(
            financial_literacy=FinancialLiteracy.BEGINNER,
        )
        saved_profile = await profile_repository.save(profile)
        current_profile.set_current_profile_id(saved_profile.id)

        use_case = SetCurrentProfileUseCase(profile_repository, profile_service, current_profile)
        request = SetCurrentProfileRequest(profile_id=None)

        response = await use_case.execute(request)

        assert response.profile is None
        assert current_profile.get_current_profile_id() is None

    @pytest.mark.asyncio
    async def test_delete_profile_use_case(
        self,
        profile_repository: AnalysisProfileRepository,
        profile_service: ProfileManagementService,
        current_profile: CurrentProfile,
    ) -> None:
        """Test deleting a profile through use case."""
        # Create a profile
        profile = AnalysisProfile(
            financial_literacy=FinancialLiteracy.BEGINNER,
            display_name="To Delete",
        )
        saved_profile = await profile_repository.save(profile)

        use_case = DeleteProfileUseCase(profile_repository, profile_service, current_profile)
        request = DeleteProfileRequest(profile_id=saved_profile.id)

        response = await use_case.execute(request)

        assert response.success is True

        # Verify profile is deleted
        retrieved = await profile_repository.get_by_id(saved_profile.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_current_profile_clears_current(
        self,
        profile_repository: AnalysisProfileRepository,
        profile_service: ProfileManagementService,
        current_profile: CurrentProfile,
    ) -> None:
        """Test that deleting the current profile clears it."""
        # Create and set a profile as current
        profile = AnalysisProfile(
            financial_literacy=FinancialLiteracy.INTERMEDIATE,
        )
        saved_profile = await profile_repository.save(profile)
        current_profile.set_current_profile_id(saved_profile.id)

        use_case = DeleteProfileUseCase(profile_repository, profile_service, current_profile)
        request = DeleteProfileRequest(profile_id=saved_profile.id)

        response = await use_case.execute(request)

        assert response.success is True
        # Verify current profile is cleared
        assert current_profile.get_current_profile_id() is None

    @pytest.mark.asyncio
    async def test_delete_profile_not_found(
        self,
        profile_repository: AnalysisProfileRepository,
        profile_service: ProfileManagementService,
        current_profile: CurrentProfile,
    ) -> None:
        """Test deleting a non-existent profile."""
        use_case = DeleteProfileUseCase(profile_repository, profile_service, current_profile)
        request = DeleteProfileRequest(profile_id=uuid4())

        response = await use_case.execute(request)

        assert response.success is False
