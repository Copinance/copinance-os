"""Storage and caching interfaces."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CacheEntry(BaseModel):
    """Cache entry with metadata."""

    schema_version: str = Field(..., description="Persistence schema version")
    data: Any = Field(..., description="Cached data")
    cached_at: datetime = Field(..., description="Timestamp when data was cached")
    tool_name: str = Field(..., description="Name of the tool that generated this data")
    cache_key: str = Field(..., description="Unique cache key for this entry")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class CacheBackend(ABC):
    """Interface for cache backends (local file, S3, etc.)."""

    @abstractmethod
    async def get(self, key: str) -> CacheEntry | None:
        """Get cached entry by key.

        Args:
            key: Cache key

        Returns:
            CacheEntry if found, None otherwise
        """
        pass

    @abstractmethod
    async def set(self, key: str, entry: CacheEntry) -> None:
        """Store cache entry.

        Args:
            key: Cache key
            entry: Cache entry to store
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete cache entry.

        Args:
            key: Cache key

        Returns:
            True if entry was deleted, False if not found
        """
        pass

    @abstractmethod
    async def clear(self, tool_name: str | None = None) -> int:
        """Clear cache entries.

        Args:
            tool_name: Optional tool name to clear only entries for that tool.
                      If None, clears all entries.

        Returns:
            Number of entries deleted
        """
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if cache entry exists.

        Args:
            key: Cache key

        Returns:
            True if entry exists, False otherwise
        """
        pass

    @abstractmethod
    def get_backend_name(self) -> str:
        """Get backend name.

        Returns:
            Backend name (e.g., 'local_file', 's3')
        """
        pass


class Storage(ABC):
    """Interface for entity storage backends (for repositories).

    This interface is used by repositories to persist domain entities.
    Different from CacheBackend which is for caching tool execution results.
    """

    @abstractmethod
    def get_collection(self, collection_name: str, entity_type: type[Any]) -> dict[UUID, Any]:
        """Get or create a collection by name.

        Args:
            collection_name: Name of the collection
            entity_type: Pydantic model type for deserialization

        Returns:
            Dictionary mapping UUIDs to entities
        """
        pass

    @abstractmethod
    def save(self, collection_name: str) -> None:
        """Save collection to disk.

        Args:
            collection_name: Name of the collection to save
        """
        pass

    @abstractmethod
    def clear(self, collection_name: str | None = None) -> None:
        """Clear storage.

        Args:
            collection_name: If provided, clear only this collection.
                           If None, clear all collections.
        """
        pass
