"""No-op cache backend for side-effect-free library use."""

from copinance_os.domain.ports.storage import CacheBackend, CacheEntry


class NullCacheBackend(CacheBackend):
    """A cache backend that never stores data and performs no I/O."""

    async def get(self, key: str) -> CacheEntry | None:
        return None

    async def set(self, key: str, entry: CacheEntry) -> None:
        return None

    async def delete(self, key: str) -> bool:
        return False

    async def clear(self, tool_name: str | None = None) -> int:
        return 0

    async def exists(self, key: str) -> bool:
        return False

    def get_backend_name(self) -> str:
        return "none"
