"""Unit tests for cache manager."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from copinanceos.domain.ports.storage import CacheBackend, CacheEntry
from copinanceos.infrastructure.cache.cache_manager import CacheManager
from copinanceos.infrastructure.cache.local_file_cache import LocalFileCacheBackend
from copinanceos.infrastructure.persistence import PERSISTENCE_SCHEMA_VERSION


@pytest.mark.unit
class TestCacheManager:
    """Test CacheManager."""

    @pytest.fixture
    def mock_backend(self) -> AsyncMock:
        """Provide a mock cache backend."""
        backend = AsyncMock(spec=CacheBackend)
        backend.get_backend_name.return_value = "mock"
        return backend

    @pytest.fixture
    def cache_manager(self, mock_backend: AsyncMock) -> CacheManager:
        """Provide a CacheManager instance with mock backend."""
        return CacheManager(backend=mock_backend)

    @pytest.fixture
    def cache_manager_with_ttl(self, mock_backend: AsyncMock) -> CacheManager:
        """Provide a CacheManager instance with TTL."""
        return CacheManager(backend=mock_backend, default_ttl=timedelta(hours=1))

    def test_init_with_backend(self, mock_backend: AsyncMock) -> None:
        """Test CacheManager initialization with backend."""
        manager = CacheManager(backend=mock_backend)
        assert manager.get_backend() == mock_backend

    def test_init_without_backend(self) -> None:
        """Test CacheManager initialization without backend (uses default)."""
        manager = CacheManager()
        assert isinstance(manager.get_backend(), LocalFileCacheBackend)

    def test_init_with_ttl(self, mock_backend: AsyncMock) -> None:
        """Test CacheManager initialization with TTL."""
        ttl = timedelta(hours=2)
        manager = CacheManager(backend=mock_backend, default_ttl=ttl)
        assert manager.get_backend() == mock_backend

    def test_generate_cache_key(self, cache_manager: CacheManager) -> None:
        """Test cache key generation."""
        key1 = cache_manager._generate_cache_key("test_tool", symbol="AAPL", period="1y")
        key2 = cache_manager._generate_cache_key("test_tool", period="1y", symbol="AAPL")
        # Same parameters in different order should generate same key
        assert key1 == key2
        assert key1.startswith(f"{PERSISTENCE_SCHEMA_VERSION}:test_tool:")

    def test_generate_cache_key_different_params(self, cache_manager: CacheManager) -> None:
        """Test cache key generation with different parameters."""
        key1 = cache_manager._generate_cache_key("test_tool", symbol="AAPL")
        key2 = cache_manager._generate_cache_key("test_tool", symbol="MSFT")
        assert key1 != key2

    async def test_get_cache_hit(
        self, cache_manager: CacheManager, mock_backend: AsyncMock
    ) -> None:
        """Test getting cached entry (cache hit)."""
        entry = CacheEntry(
            schema_version=PERSISTENCE_SCHEMA_VERSION,
            data={"price": 150.0},
            cached_at=datetime.now(UTC),
            tool_name="get_market_quote",
            cache_key="test_key",
        )
        mock_backend.get = AsyncMock(return_value=entry)

        result = await cache_manager.get("get_market_quote", symbol="AAPL")

        assert result == entry
        mock_backend.get.assert_called_once()

    async def test_get_cache_miss(
        self, cache_manager: CacheManager, mock_backend: AsyncMock
    ) -> None:
        """Test getting cached entry (cache miss)."""
        mock_backend.get = AsyncMock(return_value=None)

        result = await cache_manager.get("get_market_quote", symbol="AAPL")

        assert result is None
        mock_backend.get.assert_called_once()

    async def test_get_expired_entry(
        self, cache_manager_with_ttl: CacheManager, mock_backend: AsyncMock
    ) -> None:
        """Test getting expired cache entry."""
        expired_time = datetime.now(UTC) - timedelta(hours=2)
        entry = CacheEntry(
            schema_version=PERSISTENCE_SCHEMA_VERSION,
            data={"price": 150.0},
            cached_at=expired_time,
            tool_name="get_market_quote",
            cache_key="test_key",
        )
        mock_backend.get = AsyncMock(return_value=entry)
        mock_backend.delete = AsyncMock(return_value=True)

        result = await cache_manager_with_ttl.get("get_market_quote", symbol="AAPL", check_ttl=True)

        assert result is None
        mock_backend.delete.assert_called_once()

    async def test_get_valid_entry_with_ttl(
        self, cache_manager_with_ttl: CacheManager, mock_backend: AsyncMock
    ) -> None:
        """Test getting valid cache entry with TTL."""
        recent_time = datetime.now(UTC) - timedelta(minutes=30)
        entry = CacheEntry(
            schema_version=PERSISTENCE_SCHEMA_VERSION,
            data={"price": 150.0},
            cached_at=recent_time,
            tool_name="get_market_quote",
            cache_key="test_key",
        )
        mock_backend.get = AsyncMock(return_value=entry)

        result = await cache_manager_with_ttl.get("get_market_quote", symbol="AAPL", check_ttl=True)

        assert result == entry
        mock_backend.delete.assert_not_called()

    async def test_set(self, cache_manager: CacheManager, mock_backend: AsyncMock) -> None:
        """Test setting cache entry."""
        mock_backend.set = AsyncMock()

        await cache_manager.set("get_market_quote", {"price": 150.0}, symbol="AAPL")

        mock_backend.set.assert_called_once()
        call_args = mock_backend.set.call_args
        assert call_args[0][0].startswith(
            f"{PERSISTENCE_SCHEMA_VERSION}:get_market_quote:"
        )  # Cache key
        entry = call_args[0][1]
        assert isinstance(entry, CacheEntry)
        assert entry.schema_version == PERSISTENCE_SCHEMA_VERSION
        assert entry.data == {"price": 150.0}
        assert entry.tool_name == "get_market_quote"

    async def test_set_with_metadata(
        self, cache_manager: CacheManager, mock_backend: AsyncMock
    ) -> None:
        """Test setting cache entry with metadata."""
        mock_backend.set = AsyncMock()
        metadata = {"source": "yfinance", "version": "1.0"}

        await cache_manager.set(
            "get_market_quote", {"price": 150.0}, metadata=metadata, symbol="AAPL"
        )

        call_args = mock_backend.set.call_args
        entry = call_args[0][1]
        assert entry.metadata == metadata

    async def test_delete(self, cache_manager: CacheManager, mock_backend: AsyncMock) -> None:
        """Test deleting cache entry."""
        mock_backend.delete = AsyncMock(return_value=True)

        result = await cache_manager.delete("get_market_quote", symbol="AAPL")

        assert result is True
        mock_backend.delete.assert_called_once()

    async def test_delete_not_found(
        self, cache_manager: CacheManager, mock_backend: AsyncMock
    ) -> None:
        """Test deleting non-existent cache entry."""
        mock_backend.delete = AsyncMock(return_value=False)

        result = await cache_manager.delete("get_market_quote", symbol="AAPL")

        assert result is False

    async def test_clear(self, cache_manager: CacheManager, mock_backend: AsyncMock) -> None:
        """Test clearing cache."""
        mock_backend.clear = AsyncMock(return_value=5)

        result = await cache_manager.clear()

        assert result == 5
        mock_backend.clear.assert_called_once_with(None)

    async def test_clear_specific_tool(
        self, cache_manager: CacheManager, mock_backend: AsyncMock
    ) -> None:
        """Test clearing cache for specific tool."""
        mock_backend.clear = AsyncMock(return_value=3)

        result = await cache_manager.clear("get_market_quote")

        assert result == 3
        mock_backend.clear.assert_called_once_with("get_market_quote")

    async def test_exists(self, cache_manager: CacheManager, mock_backend: AsyncMock) -> None:
        """Test checking if cache entry exists."""
        mock_backend.exists = AsyncMock(return_value=True)

        result = await cache_manager.exists("get_market_quote", symbol="AAPL")

        assert result is True
        mock_backend.exists.assert_called_once()

    def test_get_backend(self, cache_manager: CacheManager, mock_backend: AsyncMock) -> None:
        """Test getting backend instance."""
        assert cache_manager.get_backend() == mock_backend
