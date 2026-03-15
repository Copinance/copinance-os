"""Unit tests for container storage_type and storage_path injection."""

import pytest

from copinanceos.infrastructure.containers import get_container, reset_container
from copinanceos.infrastructure.repositories.storage.memory import InMemoryStorage


@pytest.mark.unit
class TestContainerStorageConfig:
    """Validate that get_container() respects storage_type and storage_path."""

    def teardown_method(self) -> None:
        """Reset global container after each test to avoid affecting other tests."""
        reset_container()

    def test_get_container_with_storage_type_memory_uses_in_memory_storage(
        self,
    ) -> None:
        """Passing storage_type='memory' uses in-memory storage (no .copinance on disk)."""
        reset_container()
        container = get_container(
            storage_type="memory",
            load_from_env=False,
        )

        storage = container.storage_backend()
        assert isinstance(storage, InMemoryStorage)

    def test_get_container_with_storage_type_memory_and_path_ignores_path(
        self,
    ) -> None:
        """storage_path is ignored when storage_type is memory; still in-memory."""
        reset_container()
        container = get_container(
            storage_type="memory",
            storage_path="/some/path",
            load_from_env=False,
        )

        storage = container.storage_backend()
        assert isinstance(storage, InMemoryStorage)

    def test_get_container_storage_override_applied_when_container_already_exists(
        self,
    ) -> None:
        """When global container already exists, get_container(storage_type='memory') still overrides."""
        reset_container()
        get_container(load_from_env=False)
        container = get_container(
            storage_type="memory",
            load_from_env=False,
        )

        assert isinstance(container.storage_backend(), InMemoryStorage)
