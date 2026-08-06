"""Tests for explicit storage factory behavior."""

from pathlib import Path

import pytest

from copinance_os.data.repositories.storage.factory import (
    StorageType,
    create_storage,
    get_default_storage,
)
from copinance_os.data.repositories.storage.file import JsonFileStorage
from copinance_os.data.repositories.storage.memory import InMemoryStorage
from copinance_os.domain.models.common.base import Entity
from copinance_os.domain.ports.storage import Storage


class SampleEntity(Entity):
    name: str


@pytest.mark.unit
class TestStorageFactory:
    def test_default_is_memory_storage(self) -> None:
        storage = create_storage()

        assert isinstance(storage, InMemoryStorage)
        assert isinstance(storage, Storage)

    def test_get_default_storage_is_memory_and_fresh(self) -> None:
        first = get_default_storage()
        second = get_default_storage()

        assert isinstance(first, InMemoryStorage)
        assert isinstance(second, InMemoryStorage)
        assert first is not second

    def test_memory_storage_ignores_path(self, tmp_path: Path) -> None:
        storage = create_storage(storage_type=StorageType.MEMORY, base_path=tmp_path / "unused")

        assert isinstance(storage, InMemoryStorage)
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize("as_string", [False, True])
    def test_explicit_file_storage_is_lazy(self, tmp_path: Path, as_string: bool) -> None:
        path = tmp_path / "nested" / "storage"
        configured_path: Path | str = str(path) if as_string else path

        storage = create_storage(storage_type=StorageType.FILE, base_path=configured_path)

        assert isinstance(storage, JsonFileStorage)
        assert storage._base_path == path
        assert not path.exists()

    def test_file_storage_creates_directories_on_first_save(self, tmp_path: Path) -> None:
        path = tmp_path / "storage"
        storage = create_storage(storage_type=StorageType.FILE, base_path=path)
        collection = storage.get_collection("items", SampleEntity)
        entity = SampleEntity(name="one")
        collection[entity.id] = entity

        storage.save("items")

        assert (path / "data" / "v2" / "items.json").exists()

    def test_file_storage_requires_explicit_path(self) -> None:
        with pytest.raises(ValueError, match="base_path is required"):
            create_storage(storage_type=StorageType.FILE)

    def test_unknown_storage_type_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unsupported storage type"):
            create_storage(storage_type="unknown")
