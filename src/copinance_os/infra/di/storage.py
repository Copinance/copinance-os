"""Storage backend container configuration."""

from typing import Any

from dependency_injector import providers

from copinance_os.data.repositories.storage import create_storage
from copinance_os.data.repositories.storage.factory import StorageType


def configure_storage() -> providers.Singleton:
    """Configure the side-effect-free library storage provider.

    Returns:
        Singleton provider for storage backend
    """

    def _create_storage_backend() -> Any:  # Storage type, avoiding circular import
        """Create storage backend based on configuration."""
        return create_storage(storage_type=StorageType.MEMORY)

    return providers.Singleton(_create_storage_backend)
