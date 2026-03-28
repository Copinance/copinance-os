"""Profile management domain service."""

from uuid import UUID

from copinance_os.domain.exceptions import ProfileNotFoundError
from copinance_os.domain.models.profile import AnalysisProfile
from copinance_os.domain.ports.repositories import AnalysisProfileRepository


class ProfileManagementService:
    """Domain service for profile management business logic."""

    def __init__(
        self,
        profile_repository: AnalysisProfileRepository,
    ) -> None:
        """Initialize profile management service.

        Args:
            profile_repository: Repository for analysis profiles
        """
        self._profile_repository = profile_repository

    async def validate_profile_exists(self, profile_id: UUID) -> AnalysisProfile:
        """Validate that a profile exists.

        Args:
            profile_id: Profile ID to validate

        Returns:
            Analysis profile if found

        Raises:
            ProfileNotFoundError: If profile does not exist
        """
        profile = await self._profile_repository.get_by_id(profile_id)
        if profile is None:
            raise ProfileNotFoundError(str(profile_id))
        return profile

    def should_auto_set_as_current(self, profile: AnalysisProfile) -> bool:
        """Determine if a profile should be automatically set as current.

        Business rule: New profiles are automatically set as current.

        Args:
            profile: Profile to check

        Returns:
            True if profile should be auto-set as current
        """
        # Currently, all new profiles are auto-set as current
        # This could be extended with more complex business rules
        return True

    def should_clear_current_on_delete(
        self, profile_id: UUID, current_profile_id: UUID | None
    ) -> bool:
        """Determine if current profile should be cleared when deleting a profile.

        Business rule: If deleting the current profile, clear it.

        Args:
            profile_id: ID of profile being deleted
            current_profile_id: Current profile ID (if any)

        Returns:
            True if current profile should be cleared
        """
        return current_profile_id is not None and current_profile_id == profile_id
