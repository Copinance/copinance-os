"""Unit tests for JSON file storage implementation."""

import json
import os
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from copinanceos.domain.models.base import Entity
from copinanceos.domain.models.profile import AnalysisProfile, FinancialLiteracy
from copinanceos.infrastructure.persistence import get_data_dir
from copinanceos.infrastructure.repositories.storage.file import JsonFileStorage


class SampleEntity(Entity):
    """Sample entity for storage testing."""

    name: str
    value: int


@pytest.mark.unit
class TestJsonFileStorage:
    """Test JSON file storage implementation."""

    def test_init_creates_base_directory(self) -> None:
        """Test that initialization creates the base directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = Path(tmpdir) / "test_storage"
            JsonFileStorage(base_path=base_path)

            assert base_path.exists()
            assert base_path.is_dir()

    def test_init_with_string_path(self) -> None:
        """Test initialization with string path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_path = str(Path(tmpdir) / "test_storage")
            JsonFileStorage(base_path=base_path)

            assert Path(base_path).exists()

    def test_init_with_default_path(self) -> None:
        """Test initialization with default path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Change to temp directory to test default path
            old_cwd = Path.cwd()
            try:
                os.chdir(tmpdir)
                JsonFileStorage()

                assert Path(".copinance").exists()
            finally:
                os.chdir(old_cwd)

    def test_get_collection_creates_empty_collection(self) -> None:
        """Test that get_collection creates an empty collection if file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = JsonFileStorage(base_path=tmpdir)
            collection = storage.get_collection("test_collection", SampleEntity)

            assert isinstance(collection, dict)
            assert len(collection) == 0

    def test_get_collection_loads_existing_data(self) -> None:
        """Test that get_collection loads existing data from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = JsonFileStorage(base_path=tmpdir)

            # Create test entity
            entity_id = uuid4()
            entity = SampleEntity(id=entity_id, name="Test", value=42)

            # Manually save data
            collection = storage.get_collection("test_collection", SampleEntity)
            collection[entity_id] = entity
            storage.save("test_collection")

            # Create new storage instance to test loading
            storage2 = JsonFileStorage(base_path=tmpdir)
            loaded_collection = storage2.get_collection("test_collection", SampleEntity)

            assert len(loaded_collection) == 1
            assert entity_id in loaded_collection
            assert loaded_collection[entity_id].name == "Test"
            assert loaded_collection[entity_id].value == 42

    def test_get_collection_returns_same_instance(self) -> None:
        """Test that get_collection returns the same instance for multiple calls."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = JsonFileStorage(base_path=tmpdir)
            collection1 = storage.get_collection("test_collection", SampleEntity)
            collection2 = storage.get_collection("test_collection", SampleEntity)

            assert collection1 is collection2

    def test_save_persists_data_to_file(self) -> None:
        """Test that save persists data to JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = JsonFileStorage(base_path=tmpdir)

            # Create and save entities
            entity1_id = uuid4()
            entity2_id = uuid4()
            entity1 = SampleEntity(id=entity1_id, name="Entity1", value=1)
            entity2 = SampleEntity(id=entity2_id, name="Entity2", value=2)

            collection = storage.get_collection("test_collection", SampleEntity)
            collection[entity1_id] = entity1
            collection[entity2_id] = entity2

            storage.save("test_collection")

            # Verify file exists under versioned data dir and contains data
            data_dir = get_data_dir(tmpdir)
            file_path = data_dir / "test_collection.json"
            assert file_path.exists()

            with file_path.open() as f:
                data = json.load(f)

            assert "entities" in data
            entities = data["entities"]
            assert len(entities) == 2
            assert str(entity1_id) in entities
            assert str(entity2_id) in entities
            assert entities[str(entity1_id)]["name"] == "Entity1"
            assert entities[str(entity2_id)]["name"] == "Entity2"

    def test_save_handles_nonexistent_collection(self) -> None:
        """Test that save handles nonexistent collection gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = JsonFileStorage(base_path=tmpdir)

            # Should not raise an error
            storage.save("nonexistent_collection")

    def test_save_collection_early_return_when_collection_not_exists(self) -> None:
        """Test that _save_collection returns early when collection doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = JsonFileStorage(base_path=tmpdir)

            # Call _save_collection directly with nonexistent collection
            # This tests the defensive early return
            storage._save_collection("nonexistent_collection")

            # Verify no file was created (would be under data/v2)
            data_dir = get_data_dir(tmpdir)
            file_path = data_dir / "nonexistent_collection.json"
            assert not file_path.exists()

    def test_save_with_pydantic_model(self) -> None:
        """Test that save works with Pydantic models."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = JsonFileStorage(base_path=tmpdir)

            # Create AnalysisProfile entity
            profile_id = uuid4()
            profile = AnalysisProfile(
                id=profile_id,
                financial_literacy=FinancialLiteracy.INTERMEDIATE,
                display_name="Test Profile",
                preferences={"key": "value"},
            )

            collection = storage.get_collection("analysis/profiles", AnalysisProfile)
            collection[profile_id] = profile
            storage.save("analysis/profiles")

            # Verify file exists (collection "analysis/profiles" -> data/v2/analysis/profiles.json)
            data_dir = get_data_dir(tmpdir)
            file_path = data_dir / "analysis" / "profiles.json"
            assert file_path.exists()

            # Load and verify
            with file_path.open() as f:
                data = json.load(f)

            assert data["schema_version"] == "v2"
            assert str(profile_id) in data["entities"]
            assert data["entities"][str(profile_id)]["financial_literacy"] == "intermediate"
            assert data["entities"][str(profile_id)]["display_name"] == "Test Profile"

    def test_clear_single_collection(self) -> None:
        """Test that clear removes a single collection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = JsonFileStorage(base_path=tmpdir)

            # Create two collections
            entity1_id = uuid4()
            entity2_id = uuid4()
            entity1 = SampleEntity(id=entity1_id, name="Entity1", value=1)
            entity2 = SampleEntity(id=entity2_id, name="Entity2", value=2)

            collection1 = storage.get_collection("collection1", SampleEntity)
            collection2 = storage.get_collection("collection2", SampleEntity)
            collection1[entity1_id] = entity1
            collection2[entity2_id] = entity2

            storage.save("collection1")
            storage.save("collection2")

            # Clear only collection1
            storage.clear("collection1")

            # Verify collection1 is cleared
            assert len(collection1) == 0
            data_dir = get_data_dir(tmpdir)
            file_path1 = data_dir / "collection1.json"
            assert not file_path1.exists()

            # Verify collection2 still exists
            assert len(collection2) == 1
            file_path2 = data_dir / "collection2.json"
            assert file_path2.exists()

    def test_clear_all_collections(self) -> None:
        """Test that clear removes all collections when no name provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = JsonFileStorage(base_path=tmpdir)

            # Create multiple collections
            entity1_id = uuid4()
            entity2_id = uuid4()
            entity1 = SampleEntity(id=entity1_id, name="Entity1", value=1)
            entity2 = SampleEntity(id=entity2_id, name="Entity2", value=2)

            collection1 = storage.get_collection("collection1", SampleEntity)
            collection2 = storage.get_collection("collection2", SampleEntity)
            collection1[entity1_id] = entity1
            collection2[entity2_id] = entity2

            storage.save("collection1")
            storage.save("collection2")

            # Clear all
            storage.clear()

            # Verify files are removed
            data_dir = get_data_dir(tmpdir)
            file_path1 = data_dir / "collection1.json"
            file_path2 = data_dir / "collection2.json"
            assert not file_path1.exists()
            assert not file_path2.exists()

            # Verify that new collections are empty (old references may still have data)
            new_collection1 = storage.get_collection("collection1", SampleEntity)
            new_collection2 = storage.get_collection("collection2", SampleEntity)
            assert len(new_collection1) == 0
            assert len(new_collection2) == 0

    def test_clear_nonexistent_collection(self) -> None:
        """Test that clear handles nonexistent collection gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = JsonFileStorage(base_path=tmpdir)

            # Should not raise an error
            storage.clear("nonexistent_collection")

    def test_file_path_sanitization(self) -> None:
        """Test that collection names are sanitized for file paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = JsonFileStorage(base_path=tmpdir)

            # Test with special characters
            collection = storage.get_collection("test/collection", SampleEntity)
            entity_id = uuid4()
            entity = SampleEntity(id=entity_id, name="Test", value=1)
            collection[entity_id] = entity
            storage.save("test/collection")

            # Verify file uses sanitized path under data/v2 (test/collection -> test/collection.json)
            data_dir = get_data_dir(tmpdir)
            file_path = data_dir / "test" / "collection.json"
            assert file_path.exists()

    def test_load_collection_handles_corrupted_json(self, capsys) -> None:
        """Test that corrupted JSON files are handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = JsonFileStorage(base_path=tmpdir)
            data_dir = get_data_dir(tmpdir)
            data_dir.mkdir(parents=True, exist_ok=True)

            # Create a corrupted JSON file at the path storage will load from
            file_path = data_dir / "test_collection.json"
            with file_path.open("w") as f:
                f.write("invalid json content {")

            # Should not raise an error, should start fresh
            collection = storage.get_collection("test_collection", SampleEntity)

            assert isinstance(collection, dict)
            assert len(collection) == 0

            # Verify warning was printed to stderr
            captured = capsys.readouterr()
            assert "Warning" in captured.err or "Warning" in captured.out
            assert "test_collection" in captured.err or "test_collection" in captured.out

    def test_load_collection_handles_invalid_uuid(self, capsys) -> None:
        """Test that invalid UUIDs in JSON are handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = JsonFileStorage(base_path=tmpdir)
            data_dir = get_data_dir(tmpdir)
            data_dir.mkdir(parents=True, exist_ok=True)

            # Create JSON file with invalid UUID at path storage loads from
            file_path = data_dir / "test_collection.json"
            with file_path.open("w") as f:
                json.dump(
                    {
                        "schema_version": "v2",
                        "collection_name": "test_collection",
                        "entities": {"invalid-uuid": {"name": "Test", "value": 1}},
                    },
                    f,
                )

            # Should not raise an error, should start fresh
            collection = storage.get_collection("test_collection", SampleEntity)

            assert isinstance(collection, dict)
            assert len(collection) == 0

    def test_load_collection_handles_invalid_entity_data(self, capsys) -> None:
        """Test that invalid entity data in JSON is handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = JsonFileStorage(base_path=tmpdir)
            data_dir = get_data_dir(tmpdir)
            data_dir.mkdir(parents=True, exist_ok=True)

            # Create JSON file with invalid entity data at path storage loads from
            file_path = data_dir / "test_collection.json"
            entity_id = uuid4()
            with file_path.open("w") as f:
                json.dump(
                    {
                        "schema_version": "v2",
                        "collection_name": "test_collection",
                        "entities": {str(entity_id): {"invalid": "data"}},
                    },
                    f,
                )

            # Should not raise an error, should start fresh
            collection = storage.get_collection("test_collection", SampleEntity)

            assert isinstance(collection, dict)
            assert len(collection) == 0

    def test_multiple_collections_independence(self) -> None:
        """Test that multiple collections are independent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = JsonFileStorage(base_path=tmpdir)

            # Create entities in different collections
            entity1_id = uuid4()
            entity2_id = uuid4()
            entity1 = SampleEntity(id=entity1_id, name="Entity1", value=1)
            entity2 = SampleEntity(id=entity2_id, name="Entity2", value=2)

            collection1 = storage.get_collection("collection1", SampleEntity)
            collection2 = storage.get_collection("collection2", SampleEntity)

            collection1[entity1_id] = entity1
            collection2[entity2_id] = entity2

            storage.save("collection1")
            storage.save("collection2")

            # Verify independence
            assert len(collection1) == 1
            assert len(collection2) == 1
            assert entity1_id in collection1
            assert entity2_id in collection2
            assert entity1_id not in collection2
            assert entity2_id not in collection1

    def test_persistence_across_instances(self) -> None:
        """Test that data persists across different storage instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create first storage instance and save data
            storage1 = JsonFileStorage(base_path=tmpdir)
            entity_id = uuid4()
            entity = SampleEntity(id=entity_id, name="Persistent", value=100)

            collection1 = storage1.get_collection("test_collection", SampleEntity)
            collection1[entity_id] = entity
            storage1.save("test_collection")

            # Create second storage instance and load data
            storage2 = JsonFileStorage(base_path=tmpdir)
            collection2 = storage2.get_collection("test_collection", SampleEntity)

            assert len(collection2) == 1
            assert entity_id in collection2
            assert collection2[entity_id].name == "Persistent"
            assert collection2[entity_id].value == 100

    def test_save_updates_existing_file(self) -> None:
        """Test that save updates existing file with new data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = JsonFileStorage(base_path=tmpdir)

            # Create initial entity
            entity1_id = uuid4()
            entity1 = SampleEntity(id=entity1_id, name="Entity1", value=1)

            collection = storage.get_collection("test_collection", SampleEntity)
            collection[entity1_id] = entity1
            storage.save("test_collection")

            # Add another entity
            entity2_id = uuid4()
            entity2 = SampleEntity(id=entity2_id, name="Entity2", value=2)
            collection[entity2_id] = entity2
            storage.save("test_collection")

            # Verify both entities are in file
            data_dir = get_data_dir(tmpdir)
            file_path = data_dir / "test_collection.json"
            with file_path.open() as f:
                data = json.load(f)

            entities = data.get("entities", {})
            assert len(entities) == 2
            assert str(entity1_id) in entities
            assert str(entity2_id) in entities

    def test_save_updates_modified_entity(self) -> None:
        """Test that save updates modified entity data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = JsonFileStorage(base_path=tmpdir)

            # Create and save entity
            entity_id = uuid4()
            entity = SampleEntity(id=entity_id, name="Original", value=1)

            collection = storage.get_collection("test_collection", SampleEntity)
            collection[entity_id] = entity
            storage.save("test_collection")

            # Modify entity
            entity.name = "Modified"
            entity.value = 999
            storage.save("test_collection")

            # Verify modification is persisted
            storage2 = JsonFileStorage(base_path=tmpdir)
            collection2 = storage2.get_collection("test_collection", SampleEntity)

            assert collection2[entity_id].name == "Modified"
            assert collection2[entity_id].value == 999

    def test_get_collection_with_different_entity_types(self) -> None:
        """Test that get_collection works with different entity types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = JsonFileStorage(base_path=tmpdir)

            # Create collections with different entity types
            test_entity_id = uuid4()
            test_entity = SampleEntity(id=test_entity_id, name="Test", value=1)

            profile_id = uuid4()
            profile = AnalysisProfile(
                id=profile_id,
                financial_literacy=FinancialLiteracy.BEGINNER,
                display_name="Test Profile",
            )

            test_collection = storage.get_collection("test_entities", SampleEntity)
            profile_collection = storage.get_collection("analysis/profiles", AnalysisProfile)

            test_collection[test_entity_id] = test_entity
            profile_collection[profile_id] = profile

            storage.save("test_entities")
            storage.save("analysis/profiles")

            # Verify both collections work independently
            assert len(test_collection) == 1
            assert len(profile_collection) == 1
            assert isinstance(test_collection[test_entity_id], SampleEntity)
            assert isinstance(profile_collection[profile_id], AnalysisProfile)

    def test_clear_removes_file_but_not_collection_in_memory(self) -> None:
        """Test that clear removes file but collection dict remains in memory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = JsonFileStorage(base_path=tmpdir)

            entity_id = uuid4()
            entity = SampleEntity(id=entity_id, name="Test", value=1)

            collection = storage.get_collection("test_collection", SampleEntity)
            collection[entity_id] = entity
            storage.save("test_collection")

            data_dir = get_data_dir(tmpdir)
            file_path = data_dir / "test_collection.json"
            assert file_path.exists()

            # Clear collection
            storage.clear("test_collection")

            # File should be removed
            assert not file_path.exists()

            # But collection dict still exists in memory (just empty)
            assert collection is not None
            assert len(collection) == 0
