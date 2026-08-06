"""Bounded in-memory cache backend."""

from collections import OrderedDict

from copinance_os.domain.ports.storage import CacheBackend, CacheEntry


class InMemoryCacheBackend(CacheBackend):
    """Process-local LRU cache with no filesystem side effects."""

    def __init__(self, max_entries: int = 1_000) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self._max_entries = max_entries
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()

    async def get(self, key: str) -> CacheEntry | None:
        entry = self._entries.get(key)
        if entry is not None:
            self._entries.move_to_end(key)
        return entry

    async def set(self, key: str, entry: CacheEntry) -> None:
        self._entries[key] = entry
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    async def delete(self, key: str) -> bool:
        return self._entries.pop(key, None) is not None

    async def clear(self, tool_name: str | None = None) -> int:
        if tool_name is None:
            count = len(self._entries)
            self._entries.clear()
            return count
        keys = [key for key, entry in self._entries.items() if entry.tool_name == tool_name]
        for key in keys:
            del self._entries[key]
        return len(keys)

    async def exists(self, key: str) -> bool:
        return key in self._entries

    def get_backend_name(self) -> str:
        return "memory"
