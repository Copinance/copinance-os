"""Tests for side-effect-free cache backends."""

from datetime import UTC, datetime

import pytest

from copinance_os.data.cache import InMemoryCacheBackend, NullCacheBackend
from copinance_os.domain.ports.storage import CacheEntry


def _entry(key: str, tool: str = "tool") -> CacheEntry:
    return CacheEntry(
        schema_version="v2",
        data={"key": key},
        cached_at=datetime.now(UTC),
        tool_name=tool,
        cache_key=key,
    )


@pytest.mark.unit
async def test_memory_cache_evicts_least_recently_used_entry() -> None:
    backend = InMemoryCacheBackend(max_entries=2)
    await backend.set("one", _entry("one"))
    await backend.set("two", _entry("two"))
    await backend.get("one")

    await backend.set("three", _entry("three"))

    assert await backend.exists("one")
    assert not await backend.exists("two")
    assert await backend.exists("three")


@pytest.mark.unit
async def test_memory_cache_can_clear_one_tool_namespace() -> None:
    backend = InMemoryCacheBackend()
    await backend.set("one", _entry("one", "quotes"))
    await backend.set("two", _entry("two", "filings"))

    assert await backend.clear("quotes") == 1
    assert not await backend.exists("one")
    assert await backend.exists("two")


@pytest.mark.unit
async def test_null_cache_never_stores() -> None:
    backend = NullCacheBackend()

    await backend.set("key", _entry("key"))

    assert await backend.get("key") is None
    assert not await backend.exists("key")
    assert await backend.clear() == 0


@pytest.mark.unit
def test_memory_cache_requires_positive_capacity() -> None:
    with pytest.raises(ValueError, match="at least 1"):
        InMemoryCacheBackend(max_entries=0)
