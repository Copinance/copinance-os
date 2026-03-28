"""Unit tests for analysis profile repository implementation."""

from uuid import uuid4

import pytest

from copinance_os.data.repositories.profile.repository import AnalysisProfileRepositoryImpl
from copinance_os.domain.models.profile import AnalysisProfile, FinancialLiteracy
from copinance_os.domain.ports.repositories import AnalysisProfileRepository
from copinance_os.domain.ports.storage import Storage


@pytest.mark.unit
class TestAnalysisProfileRepository:
    """Test AnalysisProfileRepositoryImpl."""

    @pytest.mark.asyncio
    async def test_save_profile(
        self,
        profile_repository: AnalysisProfileRepository,
    ) -> None:
        """Test saving a profile."""
        profile = AnalysisProfile(
            financial_literacy=FinancialLiteracy.INTERMEDIATE,
            display_name="Test Investor",
            preferences={"theme": "tech"},
        )

        saved_profile = await profile_repository.save(profile)

        assert saved_profile.id == profile.id
        assert saved_profile.financial_literacy == FinancialLiteracy.INTERMEDIATE
        assert saved_profile.display_name == "Test Investor"
        assert saved_profile.preferences == {"theme": "tech"}

    @pytest.mark.asyncio
    async def test_get_profile_by_id(
        self,
        profile_repository: AnalysisProfileRepository,
    ) -> None:
        """Test retrieving a profile by ID."""
        profile = AnalysisProfile(
            financial_literacy=FinancialLiteracy.ADVANCED,
            display_name="Advanced Investor",
        )
        saved_profile = await profile_repository.save(profile)

        retrieved_profile = await profile_repository.get_by_id(saved_profile.id)

        assert retrieved_profile is not None
        assert retrieved_profile.id == saved_profile.id
        assert retrieved_profile.financial_literacy == FinancialLiteracy.ADVANCED
        assert retrieved_profile.display_name == "Advanced Investor"

    @pytest.mark.asyncio
    async def test_get_profile_by_id_not_found(
        self,
        profile_repository: AnalysisProfileRepository,
    ) -> None:
        """Test retrieving a non-existent profile returns None."""
        profile = await profile_repository.get_by_id(uuid4())

        assert profile is None

    @pytest.mark.asyncio
    async def test_update_profile(
        self,
        profile_repository: AnalysisProfileRepository,
    ) -> None:
        """Test updating an existing profile."""
        profile = AnalysisProfile(
            financial_literacy=FinancialLiteracy.BEGINNER,
            display_name="Beginner",
        )
        saved_profile = await profile_repository.save(profile)

        # Update the profile
        saved_profile.display_name = "Updated Name"
        saved_profile.financial_literacy = FinancialLiteracy.INTERMEDIATE
        updated_profile = await profile_repository.save(saved_profile)

        assert updated_profile.id == saved_profile.id
        assert updated_profile.display_name == "Updated Name"
        assert updated_profile.financial_literacy == FinancialLiteracy.INTERMEDIATE

    @pytest.mark.asyncio
    async def test_delete_profile(
        self,
        profile_repository: AnalysisProfileRepository,
    ) -> None:
        """Test deleting a profile."""
        profile = AnalysisProfile(
            financial_literacy=FinancialLiteracy.BEGINNER,
        )
        saved_profile = await profile_repository.save(profile)

        result = await profile_repository.delete(saved_profile.id)

        assert result is True

        # Verify profile is deleted
        retrieved_profile = await profile_repository.get_by_id(saved_profile.id)
        assert retrieved_profile is None

    @pytest.mark.asyncio
    async def test_delete_profile_not_found(
        self,
        profile_repository: AnalysisProfileRepository,
    ) -> None:
        """Test deleting a non-existent profile returns False."""
        result = await profile_repository.delete(uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_list_all_profiles(
        self,
        profile_repository: AnalysisProfileRepository,
    ) -> None:
        """Test listing all profiles."""
        # Create multiple profiles
        profiles = [
            AnalysisProfile(
                financial_literacy=FinancialLiteracy.BEGINNER,
                display_name=f"Profile {i}",
            )
            for i in range(5)
        ]

        for profile in profiles:
            await profile_repository.save(profile)

        all_profiles = await profile_repository.list_all()

        assert len(all_profiles) == 5
        assert all(isinstance(p, AnalysisProfile) for p in all_profiles)

    @pytest.mark.asyncio
    async def test_list_profiles_with_limit(
        self,
        profile_repository: AnalysisProfileRepository,
    ) -> None:
        """Test listing profiles with limit."""
        # Create multiple profiles
        profiles = [
            AnalysisProfile(
                financial_literacy=FinancialLiteracy.BEGINNER,
                display_name=f"Profile {i}",
            )
            for i in range(10)
        ]

        for profile in profiles:
            await profile_repository.save(profile)

        limited_profiles = await profile_repository.list_all(limit=3)

        assert len(limited_profiles) == 3

    @pytest.mark.asyncio
    async def test_list_profiles_with_offset(
        self,
        profile_repository: AnalysisProfileRepository,
    ) -> None:
        """Test listing profiles with offset."""
        # Create multiple profiles
        profiles = [
            AnalysisProfile(
                financial_literacy=FinancialLiteracy.BEGINNER,
                display_name=f"Profile {i}",
            )
            for i in range(5)
        ]

        for profile in profiles:
            await profile_repository.save(profile)

        all_profiles = await profile_repository.list_all()
        offset_profiles = await profile_repository.list_all(limit=10, offset=2)

        assert len(offset_profiles) == 3  # 5 total - 2 offset = 3
        assert offset_profiles[0].id != all_profiles[0].id

    @pytest.mark.asyncio
    async def test_list_profiles_empty(
        self,
        profile_repository: AnalysisProfileRepository,
    ) -> None:
        """Test listing profiles when none exist."""
        profiles = await profile_repository.list_all()

        assert profiles == []

    @pytest.mark.asyncio
    async def test_profile_persistence(
        self,
        isolated_storage: Storage,
    ) -> None:
        """Test that profiles persist across repository instances."""
        # Create first repository instance and save profile
        repo1 = AnalysisProfileRepositoryImpl(storage=isolated_storage)
        profile = AnalysisProfile(
            financial_literacy=FinancialLiteracy.ADVANCED,
            display_name="Persistent Profile",
        )
        saved_profile = await repo1.save(profile)

        # Create second repository instance with same storage
        repo2 = AnalysisProfileRepositoryImpl(storage=isolated_storage)

        # Verify profile can be retrieved from new instance
        retrieved_profile = await repo2.get_by_id(saved_profile.id)

        assert retrieved_profile is not None
        assert retrieved_profile.id == saved_profile.id
        assert retrieved_profile.display_name == "Persistent Profile"
