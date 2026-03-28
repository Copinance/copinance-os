"""Analysis profile-related use cases."""

from uuid import UUID

from pydantic import BaseModel, Field

from copinance_os.data.repositories.profile import CurrentProfile
from copinance_os.domain.models.profile import AnalysisProfile, FinancialLiteracy
from copinance_os.domain.ports.repositories import AnalysisProfileRepository
from copinance_os.domain.services import ProfileManagementService
from copinance_os.research.workflows.base import UseCase


class CreateProfileRequest(BaseModel):
    """Request to create a new analysis profile."""

    financial_literacy: FinancialLiteracy = Field(
        default=FinancialLiteracy.BEGINNER, description="Financial literacy level"
    )
    display_name: str | None = Field(None, description="Optional display name")
    preferences: dict[str, str] = Field(default_factory=dict, description="Analysis preferences")


class CreateProfileResponse(BaseModel):
    """Response from creating a profile."""

    profile: AnalysisProfile = Field(..., description="Created profile entity")


class CreateProfileUseCase(UseCase[CreateProfileRequest, CreateProfileResponse]):
    """Use case for creating a new analysis profile."""

    def __init__(
        self,
        profile_repository: AnalysisProfileRepository,
        profile_service: ProfileManagementService,
        current_profile: CurrentProfile | None = None,
    ) -> None:
        """Initialize use case."""
        self._profile_repository = profile_repository
        self._profile_service = profile_service
        self._current_profile = current_profile or CurrentProfile()

    async def execute(self, request: CreateProfileRequest) -> CreateProfileResponse:
        """Execute the create profile use case."""
        profile = AnalysisProfile(
            financial_literacy=request.financial_literacy,
            display_name=request.display_name,
            preferences=request.preferences,
        )

        saved_profile = await self._profile_repository.save(profile)

        # Automatically set the new profile as current (business rule)
        if self._profile_service.should_auto_set_as_current(saved_profile):
            self._current_profile.set_current_profile_id(saved_profile.id)

        return CreateProfileResponse(profile=saved_profile)


class GetProfileRequest(BaseModel):
    """Request to get a profile by ID."""

    profile_id: UUID = Field(..., description="Profile ID to retrieve")


class GetProfileResponse(BaseModel):
    """Response from getting a profile."""

    profile: AnalysisProfile | None = Field(..., description="Profile entity if found")


class GetProfileUseCase(UseCase[GetProfileRequest, GetProfileResponse]):
    """Use case for retrieving a profile by ID."""

    def __init__(self, profile_repository: AnalysisProfileRepository) -> None:
        """Initialize use case."""
        self._profile_repository = profile_repository

    async def execute(self, request: GetProfileRequest) -> GetProfileResponse:
        """Execute the get profile use case."""
        profile = await self._profile_repository.get_by_id(request.profile_id)
        return GetProfileResponse(profile=profile)


class ListProfilesRequest(BaseModel):
    """Request to list all profiles."""

    limit: int = Field(default=100, description="Maximum number of profiles to return")
    offset: int = Field(default=0, description="Offset for pagination")


class ListProfilesResponse(BaseModel):
    """Response from listing profiles."""

    profiles: list[AnalysisProfile] = Field(..., description="List of profiles")


class ListProfilesUseCase(UseCase[ListProfilesRequest, ListProfilesResponse]):
    """Use case for listing all profiles."""

    def __init__(self, profile_repository: AnalysisProfileRepository) -> None:
        """Initialize use case."""
        self._profile_repository = profile_repository

    async def execute(self, request: ListProfilesRequest) -> ListProfilesResponse:
        """Execute the list profiles use case."""
        profiles = await self._profile_repository.list_all(
            limit=request.limit, offset=request.offset
        )
        return ListProfilesResponse(profiles=profiles)


class GetCurrentProfileRequest(BaseModel):
    """Request to get the current profile."""


class GetCurrentProfileResponse(BaseModel):
    """Response from getting the current profile."""

    profile: AnalysisProfile | None = Field(..., description="Current profile if set")


class GetCurrentProfileUseCase(UseCase[GetCurrentProfileRequest, GetCurrentProfileResponse]):
    """Use case for getting the current profile."""

    def __init__(
        self,
        profile_repository: AnalysisProfileRepository,
        current_profile: CurrentProfile | None = None,
    ) -> None:
        """Initialize use case."""
        self._profile_repository = profile_repository
        self._current_profile = current_profile or CurrentProfile()

    async def execute(self, request: GetCurrentProfileRequest) -> GetCurrentProfileResponse:
        """Execute the get current profile use case."""
        current_id = self._current_profile.get_current_profile_id()
        if current_id is None:
            return GetCurrentProfileResponse(profile=None)

        profile = await self._profile_repository.get_by_id(current_id)
        return GetCurrentProfileResponse(profile=profile)


class SetCurrentProfileRequest(BaseModel):
    """Request to set the current profile."""

    profile_id: UUID | None = Field(
        None, description="Profile ID to set as current (None to clear)"
    )


class SetCurrentProfileResponse(BaseModel):
    """Response from setting the current profile."""

    profile: AnalysisProfile | None = Field(..., description="Current profile if set")


class SetCurrentProfileUseCase(UseCase[SetCurrentProfileRequest, SetCurrentProfileResponse]):
    """Use case for setting the current profile."""

    def __init__(
        self,
        profile_repository: AnalysisProfileRepository,
        profile_service: ProfileManagementService,
        current_profile: CurrentProfile | None = None,
    ) -> None:
        """Initialize use case."""
        self._profile_repository = profile_repository
        self._profile_service = profile_service
        self._current_profile = current_profile or CurrentProfile()

    async def execute(self, request: SetCurrentProfileRequest) -> SetCurrentProfileResponse:
        """Execute the set current profile use case."""
        if request.profile_id is not None:
            # Validate profile exists using domain service
            profile = await self._profile_service.validate_profile_exists(request.profile_id)
            self._current_profile.set_current_profile_id(request.profile_id)
            return SetCurrentProfileResponse(profile=profile)
        else:
            # Clear current profile
            self._current_profile.set_current_profile_id(None)
            return SetCurrentProfileResponse(profile=None)


class DeleteProfileRequest(BaseModel):
    """Request to delete a profile."""

    profile_id: UUID = Field(..., description="Profile ID to delete")


class DeleteProfileResponse(BaseModel):
    """Response from deleting a profile."""

    success: bool = Field(..., description="Whether deletion was successful")


class DeleteProfileUseCase(UseCase[DeleteProfileRequest, DeleteProfileResponse]):
    """Use case for deleting a profile."""

    def __init__(
        self,
        profile_repository: AnalysisProfileRepository,
        profile_service: ProfileManagementService,
        current_profile: CurrentProfile | None = None,
    ) -> None:
        """Initialize use case."""
        self._profile_repository = profile_repository
        self._profile_service = profile_service
        self._current_profile = current_profile or CurrentProfile()

    async def execute(self, request: DeleteProfileRequest) -> DeleteProfileResponse:
        """Execute the delete profile use case."""
        # Check if current profile should be cleared (business rule)
        current_id = self._current_profile.get_current_profile_id()
        if self._profile_service.should_clear_current_on_delete(request.profile_id, current_id):
            self._current_profile.set_current_profile_id(None)

        # Delete the profile
        success = await self._profile_repository.delete(request.profile_id)
        return DeleteProfileResponse(success=success)
