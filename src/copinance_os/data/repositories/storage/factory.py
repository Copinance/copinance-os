"""Storage factory for creating storage instances.

This factory provides storage instances without exposing the underlying
implementation technology. The factory pattern ensures that storage
details are hidden from the rest of the application.
"""

from pathlib import Path

from copinance_os.data.repositories.storage.file import JsonFileStorage
from copinance_os.data.repositories.storage.memory import InMemoryStorage
from copinance_os.domain.ports.storage import Storage


class StorageType:
    """Storage type constants."""

    FILE = "file"
    MEMORY = "memory"


def create_storage(
    storage_type: str = StorageType.FILE,
    base_path: Path | str | None = None,
) -> Storage:
    """Create a storage instance.

    This factory function creates a storage instance without revealing
    the underlying implementation. The implementation can be changed
    without affecting code that uses this factory.

    Args:
        storage_type: Type of storage backend ("file" or "memory").
                     Defaults to "file".
        base_path: Optional base path for file storage. If None, uses default.
                  Only used for file storage type.

    Returns:
        Storage instance implementing the Storage interface.

    Raises:
        ValueError: If storage_type is not supported
    """
    if storage_type == StorageType.FILE:
        if base_path is None:
            return JsonFileStorage()
        return JsonFileStorage(base_path=base_path)
    elif storage_type == StorageType.MEMORY:
        return InMemoryStorage()
    else:
        raise ValueError(
            f"Unsupported storage type: {storage_type}. "
            f"Supported types: {StorageType.FILE}, {StorageType.MEMORY}"
        )


def get_default_storage() -> Storage:
    """Get the default storage instance.

    Returns:
        Default Storage instance for the application (file-based).
    """
    return JsonFileStorage()
