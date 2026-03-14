"""Research profile repository implementation."""

from uuid import UUID

from copinanceos.domain.models.research_profile import ResearchProfile
from copinanceos.domain.ports.repositories import ResearchProfileRepository
from copinanceos.domain.ports.storage import Storage
from copinanceos.infrastructure.repositories.storage.factory import create_storage


class ResearchProfileRepositoryImpl(ResearchProfileRepository):
    """Implementation of ResearchProfileRepository.

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
        self._collection = self._storage.get_collection("research/profiles", ResearchProfile)

    async def get_by_id(self, profile_id: UUID) -> ResearchProfile | None:
        """Get research profile by ID."""
        return self._collection.get(profile_id)

    async def save(self, profile: ResearchProfile) -> ResearchProfile:
        """Save or update research profile."""
        self._collection[profile.id] = profile
        self._storage.save("research/profiles")
        return profile

    async def delete(self, profile_id: UUID) -> bool:
        """Delete research profile by ID."""
        if profile_id in self._collection:
            del self._collection[profile_id]
            self._storage.save("research/profiles")
            return True
        return False

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[ResearchProfile]:
        """List all profiles with pagination."""
        all_profiles = list(self._collection.values())
        return all_profiles[offset : offset + limit]
