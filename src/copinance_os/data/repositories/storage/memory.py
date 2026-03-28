"""In-memory storage backend for repositories.

This storage backend stores data in memory only. Data is lost when the process exits.
Suitable for testing and temporary use cases.
"""

from typing import Any
from uuid import UUID

from copinance_os.domain.ports.storage import Storage


class InMemoryStorage(Storage):
    """In-memory storage backend.

    This storage backend stores data in memory only. Data is lost when
    the process exits. Suitable for testing and temporary use cases.
    """

    def __init__(self) -> None:
        """Initialize in-memory storage."""
        self._collections: dict[str, dict[UUID, Any]] = {}

    def get_collection(self, collection_name: str, entity_type: type[Any]) -> dict[UUID, Any]:
        """Get or create a collection by name.

        Args:
            collection_name: Name of the collection
            entity_type: Pydantic model type for deserialization (not used in memory storage)

        Returns:
            Dictionary mapping UUIDs to entities
        """
        if collection_name not in self._collections:
            self._collections[collection_name] = {}
        return self._collections[collection_name]

    def save(self, collection_name: str) -> None:
        """Save collection to disk.

        For in-memory storage, this is a no-op since data is already in memory.

        Args:
            collection_name: Name of the collection to save
        """
        # No-op for in-memory storage
        pass

    def clear(self, collection_name: str | None = None) -> None:
        """Clear storage.

        Args:
            collection_name: If provided, clear only this collection.
                           If None, clear all collections.
        """
        if collection_name is None:
            self._collections.clear()
        elif collection_name in self._collections:
            self._collections[collection_name].clear()
