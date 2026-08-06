"""Unit tests for container storage_type and storage_path injection."""

import pytest

from copinance_os.data.repositories.storage.memory import InMemoryStorage
from copinance_os.infra.di import create_container


@pytest.mark.unit
class TestContainerStorageConfig:
    """Validate explicit storage composition."""

    def test_create_container_with_storage_type_memory_uses_in_memory_storage(
        self,
    ) -> None:
        """Passing storage_type='memory' uses in-memory storage (no .copinance on disk)."""
        container = create_container()

        storage = container.storage_backend()
        assert isinstance(storage, InMemoryStorage)

    def test_create_container_with_storage_type_memory_and_path_ignores_path(
        self,
    ) -> None:
        """storage_path is ignored when storage_type is memory; still in-memory."""
        container = create_container(
            storage_type="memory",
            storage_path="/some/path",
        )

        storage = container.storage_backend()
        assert isinstance(storage, InMemoryStorage)

    def test_file_storage_requires_an_explicit_path(self) -> None:
        with pytest.raises(ValueError, match="storage_path is required"):
            create_container(storage_type="file")
