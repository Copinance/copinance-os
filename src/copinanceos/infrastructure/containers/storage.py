"""Storage backend container configuration."""

from typing import Any

from dependency_injector import providers

from copinanceos.infrastructure.config import get_settings, get_storage_path_safe
from copinanceos.infrastructure.repositories.storage import create_storage


def configure_storage() -> providers.Singleton:
    """Configure storage backend provider.

    Returns:
        Singleton provider for storage backend
    """

    def _create_storage_backend() -> Any:  # Storage type, avoiding circular import
        """Create storage backend based on configuration."""
        settings = get_settings()
        return create_storage(
            storage_type=settings.storage_type,
            base_path=get_storage_path_safe(),
        )

    return providers.Singleton(_create_storage_backend)
