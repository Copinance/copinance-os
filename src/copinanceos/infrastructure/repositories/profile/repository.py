"""Analysis profile repository implementation."""

from uuid import UUID

from copinanceos.domain.models.profile import AnalysisProfile
from copinanceos.domain.ports.repositories import AnalysisProfileRepository
from copinanceos.domain.ports.storage import Storage
from copinanceos.infrastructure.repositories.storage.factory import create_storage


class AnalysisProfileRepositoryImpl(AnalysisProfileRepository):
    """Implementation of AnalysisProfileRepository.

    This repository uses the Storage interface, hiding the underlying
    storage implementation. The storage technology is not exposed
    to consumers of this repository.
    """

    def __init__(self, storage: Storage | None = None) -> None:
        """Initialize repository.

        Args:
            storage: Optional storage backend. If None, creates default storage.
                     Should implement the Storage interface.
        """
        if storage is None:
            storage = create_storage()
        self._storage = storage
        self._collection = self._storage.get_collection("analysis/profiles", AnalysisProfile)

    async def get_by_id(self, profile_id: UUID) -> AnalysisProfile | None:
        """Get analysis profile by ID."""
        return self._collection.get(profile_id)

    async def save(self, profile: AnalysisProfile) -> AnalysisProfile:
        """Save or update analysis profile."""
        self._collection[profile.id] = profile
        self._storage.save("analysis/profiles")
        return profile

    async def delete(self, profile_id: UUID) -> bool:
        """Delete analysis profile by ID."""
        if profile_id in self._collection:
            del self._collection[profile_id]
            self._storage.save("analysis/profiles")
            return True
        return False

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[AnalysisProfile]:
        """List all profiles with pagination."""
        all_profiles = list(self._collection.values())
        return all_profiles[offset : offset + limit]
