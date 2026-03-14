"""Cache manager for tool data caching."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from copinanceos.domain.ports.storage import CacheBackend, CacheEntry
from copinanceos.infrastructure.cache.local_file_cache import LocalFileCacheBackend
from copinanceos.infrastructure.persistence import PERSISTENCE_SCHEMA_VERSION

logger = structlog.get_logger(__name__)


class CacheManager:
    """Manages caching for tool execution results.

    Provides a unified interface for caching tool data with support for
    different backends (local file, S3, etc.).
    """

    def __init__(
        self, backend: CacheBackend | None = None, default_ttl: timedelta | None = None
    ) -> None:
        """Initialize cache manager.

        Args:
            backend: Cache backend instance. If None, uses LocalFileCacheBackend.
            default_ttl: Default time-to-live for cache entries. If None, no expiration.
        """
        self._backend = backend or LocalFileCacheBackend()
        self._default_ttl = default_ttl
        logger.info(
            "Initialized cache manager",
            backend=self._backend.get_backend_name(),
            default_ttl_seconds=self._default_ttl.total_seconds() if self._default_ttl else None,
        )

    def _generate_cache_key(self, tool_name: str, **kwargs: Any) -> str:
        """Generate cache key from tool name and parameters.

        Args:
            tool_name: Name of the tool
            **kwargs: Tool parameters

        Returns:
            Cache key string
        """
        # Sort kwargs for consistent key generation
        sorted_params = sorted(kwargs.items())
        params_str = json.dumps(sorted_params, sort_keys=True, default=str)
        key_data = f"{PERSISTENCE_SCHEMA_VERSION}:{tool_name}:{params_str}"
        key_hash = hashlib.sha256(key_data.encode()).hexdigest()
        return f"{PERSISTENCE_SCHEMA_VERSION}:{tool_name}:{key_hash}"

    async def get(
        self,
        tool_name: str,
        check_ttl: bool = True,
        **kwargs: Any,
    ) -> CacheEntry | None:
        """Get cached entry for tool execution.

        Args:
            tool_name: Name of the tool
            check_ttl: Whether to check TTL and return None if expired
            **kwargs: Tool parameters

        Returns:
            CacheEntry if found and valid, None otherwise
        """
        cache_key = self._generate_cache_key(tool_name, **kwargs)
        entry = await self._backend.get(cache_key)

        if entry is None:
            return None

        # Check TTL if enabled
        if check_ttl and self._default_ttl:
            age = datetime.now(UTC) - entry.cached_at
            if age > self._default_ttl:
                logger.debug("Cache entry expired", key=cache_key, age_seconds=age.total_seconds())
                await self._backend.delete(cache_key)
                return None

        return entry

    async def set(
        self,
        tool_name: str,
        data: Any,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Store tool execution result in cache.

        Args:
            tool_name: Name of the tool
            data: Data to cache
            metadata: Optional metadata to include
            **kwargs: Tool parameters
        """
        cache_key = self._generate_cache_key(tool_name, **kwargs)
        entry = CacheEntry(
            schema_version=PERSISTENCE_SCHEMA_VERSION,
            data=data,
            cached_at=datetime.now(UTC),
            tool_name=tool_name,
            cache_key=cache_key,
            metadata=metadata or {},
        )

        await self._backend.set(cache_key, entry)

    async def delete(self, tool_name: str, **kwargs: Any) -> bool:
        """Delete cached entry.

        Args:
            tool_name: Name of the tool
            **kwargs: Tool parameters

        Returns:
            True if entry was deleted, False if not found
        """
        cache_key = self._generate_cache_key(tool_name, **kwargs)
        return await self._backend.delete(cache_key)

    async def clear(self, tool_name: str | None = None) -> int:
        """Clear cache entries.

        Args:
            tool_name: Optional tool name to clear only entries for that tool.
                      If None, clears all entries.

        Returns:
            Number of entries deleted
        """
        return await self._backend.clear(tool_name)

    async def exists(self, tool_name: str, **kwargs: Any) -> bool:
        """Check if cache entry exists.

        Args:
            tool_name: Name of the tool
            **kwargs: Tool parameters

        Returns:
            True if entry exists, False otherwise
        """
        cache_key = self._generate_cache_key(tool_name, **kwargs)
        return await self._backend.exists(cache_key)

    def get_backend(self) -> CacheBackend:
        """Get the cache backend instance.

        Returns:
            Cache backend instance
        """
        return self._backend
