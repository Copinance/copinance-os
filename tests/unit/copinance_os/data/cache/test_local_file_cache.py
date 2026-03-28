"""Unit tests for local file cache backend."""

import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from copinance_os.data.cache.local_file_cache import LocalFileCacheBackend
from copinance_os.data.loaders.persistence import PERSISTENCE_SCHEMA_VERSION
from copinance_os.domain.ports.storage import CacheEntry


@pytest.mark.unit
class TestLocalFileCacheBackend:
    """Test LocalFileCacheBackend."""

    @pytest.fixture
    def temp_cache_dir(self) -> Path:
        """Provide a temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def cache_backend(self, temp_cache_dir: Path) -> LocalFileCacheBackend:
        """Provide a LocalFileCacheBackend instance."""
        return LocalFileCacheBackend(cache_dir=temp_cache_dir)

    def test_init_with_cache_dir(self, temp_cache_dir: Path) -> None:
        """Test initialization with cache directory."""
        backend = LocalFileCacheBackend(cache_dir=temp_cache_dir)
        assert backend._cache_dir == temp_cache_dir
        assert temp_cache_dir.exists()

    def test_init_with_string_path(self) -> None:
        """Test initialization with string path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = LocalFileCacheBackend(cache_dir=str(tmpdir))
            assert backend._cache_dir == Path(tmpdir)

    @patch("copinance_os.data.cache.local_file_cache.create_storage")
    def test_init_without_cache_dir(self, mock_create_storage: patch) -> None:
        """Test initialization without cache directory (uses default)."""
        mock_storage = MagicMock()
        mock_storage._root_path = Path(".copinance")
        mock_create_storage.return_value = mock_storage

        backend = LocalFileCacheBackend()
        assert backend._cache_dir == Path(".copinance") / "cache" / "v2"

    def test_get_backend_name(self, cache_backend: LocalFileCacheBackend) -> None:
        """Test getting backend name."""
        assert cache_backend.get_backend_name() == "local_file"

    def test_get_cache_file_path(self, cache_backend: LocalFileCacheBackend) -> None:
        """Test cache file path generation."""
        path = cache_backend._get_cache_file_path("test_key")
        assert str(path).startswith(str(cache_backend._cache_dir))
        assert path.suffix == ".json"
        # Path should be based on hash of key
        assert len(path.stem) == 64  # SHA256 hex digest length

    async def test_get_cache_miss(self, cache_backend: LocalFileCacheBackend) -> None:
        """Test getting non-existent cache entry."""
        result = await cache_backend.get("nonexistent_key")
        assert result is None

    async def test_set_and_get(self, cache_backend: LocalFileCacheBackend) -> None:
        """Test setting and getting cache entry."""
        entry = CacheEntry(
            schema_version=PERSISTENCE_SCHEMA_VERSION,
            data={"price": 150.0},
            cached_at=datetime.now(UTC),
            tool_name="get_market_quote",
            cache_key="test_key",
        )

        await cache_backend.set("test_key", entry)
        result = await cache_backend.get("test_key")

        assert result is not None
        assert result.data == entry.data
        assert result.tool_name == entry.tool_name
        assert result.cache_key == entry.cache_key

    async def test_set_and_get_with_metadata(self, cache_backend: LocalFileCacheBackend) -> None:
        """Test setting and getting cache entry with metadata."""
        metadata = {"source": "yfinance", "version": "1.0"}
        entry = CacheEntry(
            schema_version=PERSISTENCE_SCHEMA_VERSION,
            data={"price": 150.0},
            cached_at=datetime.now(UTC),
            tool_name="get_market_quote",
            cache_key="test_key",
            metadata=metadata,
        )

        await cache_backend.set("test_key", entry)
        result = await cache_backend.get("test_key")

        assert result is not None
        # Backend may add cache_file_path; original metadata must be preserved
        assert result.metadata.get("source") == metadata["source"]
        assert result.metadata.get("version") == metadata["version"]

    async def test_delete_existing(self, cache_backend: LocalFileCacheBackend) -> None:
        """Test deleting existing cache entry."""
        entry = CacheEntry(
            schema_version=PERSISTENCE_SCHEMA_VERSION,
            data={"price": 150.0},
            cached_at=datetime.now(UTC),
            tool_name="get_market_quote",
            cache_key="test_key",
        )

        await cache_backend.set("test_key", entry)
        result = await cache_backend.delete("test_key")

        assert result is True
        assert await cache_backend.get("test_key") is None

    async def test_delete_nonexistent(self, cache_backend: LocalFileCacheBackend) -> None:
        """Test deleting non-existent cache entry."""
        result = await cache_backend.delete("nonexistent_key")
        assert result is False

    async def test_clear_all(self, cache_backend: LocalFileCacheBackend) -> None:
        """Test clearing all cache entries."""
        # Create multiple entries
        for i in range(3):
            entry = CacheEntry(
                schema_version=PERSISTENCE_SCHEMA_VERSION,
                data={"value": i},
                cached_at=datetime.now(UTC),
                tool_name=f"tool_{i}",
                cache_key=f"key_{i}",
            )
            await cache_backend.set(f"key_{i}", entry)

        result = await cache_backend.clear()

        assert result == 3
        # Verify all entries are gone
        for i in range(3):
            assert await cache_backend.get(f"key_{i}") is None

    async def test_clear_specific_tool(self, cache_backend: LocalFileCacheBackend) -> None:
        """Test clearing cache entries for specific tool."""
        # Create entries for different tools
        for i in range(3):
            entry = CacheEntry(
                schema_version=PERSISTENCE_SCHEMA_VERSION,
                data={"value": i},
                cached_at=datetime.now(UTC),
                tool_name="get_market_quote",
                cache_key=f"key_{i}",
            )
            await cache_backend.set(f"key_{i}", entry)

        # Create entry for different tool
        other_entry = CacheEntry(
            schema_version=PERSISTENCE_SCHEMA_VERSION,
            data={"value": 999},
            cached_at=datetime.now(UTC),
            tool_name="get_fundamentals",
            cache_key="other_key",
        )
        await cache_backend.set("other_key", other_entry)

        result = await cache_backend.clear("get_market_quote")

        assert result == 3
        # Verify get_market_quote entries are gone
        for i in range(3):
            assert await cache_backend.get(f"key_{i}") is None
        # Verify other tool entry still exists
        assert await cache_backend.get("other_key") is not None

    async def test_exists(self, cache_backend: LocalFileCacheBackend) -> None:
        """Test checking if cache entry exists."""
        entry = CacheEntry(
            schema_version=PERSISTENCE_SCHEMA_VERSION,
            data={"price": 150.0},
            cached_at=datetime.now(UTC),
            tool_name="get_market_quote",
            cache_key="test_key",
        )

        assert await cache_backend.exists("test_key") is False
        await cache_backend.set("test_key", entry)
        assert await cache_backend.exists("test_key") is True

    async def test_get_corrupted_file(self, cache_backend: LocalFileCacheBackend) -> None:
        """Test getting cache entry from corrupted file."""
        # Create a corrupted cache file
        cache_file = cache_backend._get_cache_file_path("corrupted_key")
        cache_file.write_text("invalid json")

        result = await cache_backend.get("corrupted_key")

        assert result is None

    async def test_set_handles_io_error(self, cache_backend: LocalFileCacheBackend) -> None:
        """Test that set raises exception on IO error."""
        # Make cache directory read-only to cause IO error
        cache_backend._cache_dir.chmod(0o444)
        try:
            entry = CacheEntry(
                schema_version=PERSISTENCE_SCHEMA_VERSION,
                data={"price": 150.0},
                cached_at=datetime.now(UTC),
                tool_name="get_market_quote",
                cache_key="test_key",
            )

            with pytest.raises(OSError):  # Should raise OSError or PermissionError
                await cache_backend.set("test_key", entry)
        finally:
            # Restore permissions
            cache_backend._cache_dir.chmod(0o755)
