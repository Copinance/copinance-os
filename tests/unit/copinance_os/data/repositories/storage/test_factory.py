"""Unit tests for storage factory."""

import tempfile
from pathlib import Path

import pytest

from copinance_os.data.repositories.storage.factory import (
    create_storage,
    get_default_storage,
)
from copinance_os.data.repositories.storage.file import JsonFileStorage
from copinance_os.domain.models.base import Entity
from copinance_os.domain.ports.storage import Storage


@pytest.mark.unit
class TestStorageFactory:
    """Test storage factory functions."""

    def test_create_storage_with_none_returns_default(self) -> None:
        """Test that create_storage with None returns storage with default path."""
        storage = create_storage(base_path=None)

        assert isinstance(storage, JsonFileStorage)
        assert isinstance(storage, Storage)
        # Verify it uses default path
        assert storage._base_path == Path(".copinance")

    def test_create_storage_with_path_object(self) -> None:
        """Test that create_storage accepts Path object."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "custom_storage"
            storage = create_storage(base_path=base_path)

            assert isinstance(storage, JsonFileStorage)
            assert isinstance(storage, Storage)
            assert storage._base_path == base_path
            # Verify directory was created
            assert base_path.exists()
            assert base_path.is_dir()

    def test_create_storage_with_string_path(self) -> None:
        """Test that create_storage accepts string path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path_str = str(Path(tmpdir) / "string_storage")
            storage = create_storage(base_path=base_path_str)

            assert isinstance(storage, JsonFileStorage)
            assert isinstance(storage, Storage)
            assert storage._base_path == Path(base_path_str)
            # Verify directory was created
            assert Path(base_path_str).exists()

    def test_create_storage_with_nested_path(self) -> None:
        """Test that create_storage creates nested directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "nested" / "storage" / "path"
            storage = create_storage(base_path=base_path)

            assert isinstance(storage, JsonFileStorage)
            assert base_path.exists()
            assert base_path.is_dir()

    def test_create_storage_returns_functional_storage(self) -> None:
        """Test that create_storage returns a functional storage instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = create_storage(base_path=tmpdir)

            # Verify it implements Storage interface
            assert hasattr(storage, "get_collection")
            assert hasattr(storage, "save")
            assert hasattr(storage, "clear")

            # Verify it's functional
            class TestEntity(Entity):
                name: str

            collection = storage.get_collection("test", TestEntity)
            assert isinstance(collection, dict)

    def test_get_default_storage_returns_storage(self) -> None:
        """Test that get_default_storage returns a storage instance."""
        storage = get_default_storage()

        assert isinstance(storage, JsonFileStorage)
        assert isinstance(storage, Storage)

    def test_get_default_storage_uses_default_path(self) -> None:
        """Test that get_default_storage uses default path."""
        storage = get_default_storage()

        assert storage._base_path == Path(".copinance")

    def test_get_default_storage_returns_functional_storage(self) -> None:
        """Test that get_default_storage returns a functional storage instance."""
        storage = get_default_storage()

        # Verify it implements Storage interface
        assert hasattr(storage, "get_collection")
        assert hasattr(storage, "save")
        assert hasattr(storage, "clear")

        # Verify it's functional
        class TestEntity(Entity):
            name: str

        collection = storage.get_collection("test", TestEntity)
        assert isinstance(collection, dict)

    def test_create_storage_and_get_default_storage_return_same_type(self) -> None:
        """Test that both factory functions return the same storage type."""
        storage1 = create_storage()
        storage2 = get_default_storage()

        assert type(storage1) is type(storage2)
        assert isinstance(storage1, JsonFileStorage)
        assert isinstance(storage2, JsonFileStorage)

    def test_create_storage_with_different_paths_creates_separate_instances(self) -> None:
        """Test that create_storage with different paths creates separate instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path1 = Path(tmpdir) / "storage1"
            path2 = Path(tmpdir) / "storage2"

            storage1 = create_storage(base_path=path1)
            storage2 = create_storage(base_path=path2)

            assert storage1 is not storage2
            assert storage1._base_path != storage2._base_path
            assert storage1._base_path == path1
            assert storage2._base_path == path2

    def test_create_storage_with_same_path_creates_separate_instances(self) -> None:
        """Test that create_storage with same path creates separate instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "shared_storage"

            storage1 = create_storage(base_path=path)
            storage2 = create_storage(base_path=path)

            # Should be separate instances but use same path
            assert storage1 is not storage2
            assert storage1._base_path == storage2._base_path
            assert storage1._base_path == path

    def test_create_storage_with_empty_string(self) -> None:
        """Test that create_storage handles empty string path."""
        storage = create_storage(base_path="")

        assert isinstance(storage, JsonFileStorage)
        assert storage._base_path == Path()

    def test_get_default_storage_creates_new_instance_each_time(self) -> None:
        """Test that get_default_storage creates a new instance each time."""
        storage1 = get_default_storage()
        storage2 = get_default_storage()

        # Should be separate instances
        assert storage1 is not storage2
        # But should use same default path
        assert storage1._base_path == storage2._base_path
