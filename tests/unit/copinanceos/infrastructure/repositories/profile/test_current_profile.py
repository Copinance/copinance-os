"""Unit tests for CurrentProfile state management."""

import json
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from copinanceos.domain.ports.storage import Storage
from copinanceos.infrastructure.persistence import PERSISTENCE_SCHEMA_VERSION
from copinanceos.infrastructure.repositories.profile.current_profile import (
    CurrentProfile,
    _get_config_path,
)
from copinanceos.infrastructure.repositories.storage.file import JsonFileStorage


@pytest.fixture
def temp_storage_path() -> Path:
    """Provide a temporary directory for storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def config_file_path(temp_storage_path: Path) -> Path:
    """Provide a config file path in temp directory."""
    path = temp_storage_path / "state" / "v2" / "app.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@pytest.mark.unit
class TestCurrentProfile:
    """Test CurrentProfile state management."""

    def test_get_current_profile_id_when_not_set(self, config_file_path: Path) -> None:
        """Test getting current profile ID when none is set."""
        # Ensure file doesn't exist
        if config_file_path.exists():
            config_file_path.unlink()

        # Mock the config path
        with patch(
            "copinanceos.infrastructure.repositories.profile.current_profile._get_config_path"
        ) as mock_path:
            mock_path.return_value = config_file_path

            profile = CurrentProfile()
            result = profile.get_current_profile_id()

            assert result is None

    def test_set_and_get_current_profile_id(self, config_file_path: Path) -> None:
        """Test setting and getting current profile ID."""
        profile_id = uuid4()

        # Mock the config path
        with patch(
            "copinanceos.infrastructure.repositories.profile.current_profile._get_config_path"
        ) as mock_path:
            mock_path.return_value = config_file_path

            profile = CurrentProfile()
            profile.set_current_profile_id(profile_id)

            retrieved_id = profile.get_current_profile_id()

            assert retrieved_id == profile_id

    def test_clear_current_profile_id(self, config_file_path: Path) -> None:
        """Test clearing current profile ID."""
        profile_id = uuid4()

        # Mock the config path
        with patch(
            "copinanceos.infrastructure.repositories.profile.current_profile._get_config_path"
        ) as mock_path:
            mock_path.return_value = config_file_path

            profile = CurrentProfile()
            # Set a profile ID first
            profile.set_current_profile_id(profile_id)
            assert profile.get_current_profile_id() == profile_id

            # Clear it
            profile.set_current_profile_id(None)

            # Verify it's cleared
            assert profile.get_current_profile_id() is None

    def test_update_current_profile_id(self, config_file_path: Path) -> None:
        """Test updating current profile ID."""
        profile_id1 = uuid4()
        profile_id2 = uuid4()

        # Mock the config path
        with patch(
            "copinanceos.infrastructure.repositories.profile.current_profile._get_config_path"
        ) as mock_path:
            mock_path.return_value = config_file_path

            profile = CurrentProfile()
            profile.set_current_profile_id(profile_id1)
            assert profile.get_current_profile_id() == profile_id1

            profile.set_current_profile_id(profile_id2)
            assert profile.get_current_profile_id() == profile_id2

    def test_persist_current_profile_id(self, config_file_path: Path) -> None:
        """Test that current profile ID persists across instances."""
        profile_id = uuid4()

        # Mock the config path
        with patch(
            "copinanceos.infrastructure.repositories.profile.current_profile._get_config_path"
        ) as mock_path:
            mock_path.return_value = config_file_path

            # Set profile ID with first instance
            profile1 = CurrentProfile()
            profile1.set_current_profile_id(profile_id)

            # Get profile ID with second instance
            profile2 = CurrentProfile()
            retrieved_id = profile2.get_current_profile_id()

            assert retrieved_id == profile_id

    def test_handle_invalid_json(self, config_file_path: Path) -> None:
        """Test handling invalid JSON in config file."""
        config_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write invalid JSON
        config_file_path.write_text("invalid json content")

        # Mock the config path
        with patch(
            "copinanceos.infrastructure.repositories.profile.current_profile._get_config_path"
        ) as mock_path:
            mock_path.return_value = config_file_path

            profile = CurrentProfile()
            # Should return None when JSON is invalid
            result = profile.get_current_profile_id()

            assert result is None

            # Should be able to set a new value
            profile_id = uuid4()
            profile.set_current_profile_id(profile_id)
            assert profile.get_current_profile_id() == profile_id

    def test_handle_invalid_uuid(self, config_file_path: Path) -> None:
        """Test handling invalid UUID in config file."""
        config_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write config with invalid UUID
        config = {
            "schema_version": PERSISTENCE_SCHEMA_VERSION,
            "current_profile_id": "not-a-valid-uuid",
        }
        config_file_path.write_text(json.dumps(config))

        # Mock the config path
        with patch(
            "copinanceos.infrastructure.repositories.profile.current_profile._get_config_path"
        ) as mock_path:
            mock_path.return_value = config_file_path

            profile = CurrentProfile()
            # Should return None when UUID is invalid
            result = profile.get_current_profile_id()

            assert result is None

    def test_get_current_profile_id_with_empty_config(self, config_file_path: Path) -> None:
        """Test getting current profile ID when config file has empty dict."""
        config_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write empty config
        config_file_path.write_text(json.dumps({"schema_version": PERSISTENCE_SCHEMA_VERSION}))

        # Mock the config path
        with patch(
            "copinanceos.infrastructure.repositories.profile.current_profile._get_config_path"
        ) as mock_path:
            mock_path.return_value = config_file_path

            profile = CurrentProfile()
            result = profile.get_current_profile_id()

            assert result is None

    def test_get_current_profile_id_with_other_keys(self, config_file_path: Path) -> None:
        """Test getting current profile ID when config has other keys but no current_profile_id."""
        config_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write config with other keys
        config = {
            "schema_version": PERSISTENCE_SCHEMA_VERSION,
            "other_key": "value",
            "another_key": 123,
        }
        config_file_path.write_text(json.dumps(config))

        # Mock the config path
        with patch(
            "copinanceos.infrastructure.repositories.profile.current_profile._get_config_path"
        ) as mock_path:
            mock_path.return_value = config_file_path

            profile = CurrentProfile()
            result = profile.get_current_profile_id()

            assert result is None

    def test_set_current_profile_id_preserves_other_keys(self, config_file_path: Path) -> None:
        """Test that setting current profile ID preserves other config keys."""
        config_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write config with other keys
        original_config = {
            "schema_version": PERSISTENCE_SCHEMA_VERSION,
            "other_key": "value",
            "another_key": 123,
        }
        config_file_path.write_text(json.dumps(original_config))

        profile_id = uuid4()

        # Mock the config path
        with patch(
            "copinanceos.infrastructure.repositories.profile.current_profile._get_config_path"
        ) as mock_path:
            mock_path.return_value = config_file_path

            profile = CurrentProfile()
            profile.set_current_profile_id(profile_id)

            # Verify profile ID was set
            assert profile.get_current_profile_id() == profile_id

            # Verify other keys are preserved
            with open(config_file_path) as f:
                updated_config = json.load(f)
                assert updated_config["schema_version"] == PERSISTENCE_SCHEMA_VERSION
                assert updated_config["other_key"] == "value"
                assert updated_config["another_key"] == 123
                assert updated_config["current_profile_id"] == str(profile_id)

    def test_clear_current_profile_id_preserves_other_keys(self, config_file_path: Path) -> None:
        """Test that clearing current profile ID preserves other config keys."""
        config_file_path.parent.mkdir(parents=True, exist_ok=True)

        profile_id = uuid4()
        original_config = {
            "schema_version": PERSISTENCE_SCHEMA_VERSION,
            "current_profile_id": str(profile_id),
            "other_key": "value",
            "another_key": 123,
        }
        config_file_path.write_text(json.dumps(original_config))

        # Mock the config path
        with patch(
            "copinanceos.infrastructure.repositories.profile.current_profile._get_config_path"
        ) as mock_path:
            mock_path.return_value = config_file_path

            profile = CurrentProfile()
            profile.set_current_profile_id(None)

            # Verify profile ID was cleared
            assert profile.get_current_profile_id() is None

            # Verify other keys are preserved
            with open(config_file_path) as f:
                updated_config = json.load(f)
                assert updated_config["schema_version"] == PERSISTENCE_SCHEMA_VERSION
                assert updated_config["other_key"] == "value"
                assert updated_config["another_key"] == 123
                assert "current_profile_id" not in updated_config

    def test_get_config_path_with_json_file_storage(self, temp_storage_path: Path) -> None:
        """Test _get_config_path with JsonFileStorage."""
        # Patch create_storage to return storage with temp path
        with patch(
            "copinanceos.infrastructure.repositories.profile.current_profile.create_storage"
        ) as mock_create_storage:
            mock_create_storage.return_value = JsonFileStorage(base_path=temp_storage_path)
            config_path = _get_config_path()

            # Should use storage's base path
            assert config_path.parent == temp_storage_path / "state" / "v2"
            assert config_path.name == "app.json"
            # Directory should be created
            assert temp_storage_path.exists()
            assert temp_storage_path.is_dir()

    def test_get_config_path_with_non_json_storage(self) -> None:
        """Test _get_config_path when storage is not JsonFileStorage."""
        mock_storage = MagicMock(spec=Storage)
        # Mock doesn't have _base_path attribute

        with patch(
            "copinanceos.infrastructure.repositories.profile.current_profile.create_storage"
        ) as mock_create_storage:
            mock_create_storage.return_value = mock_storage

            config_path = _get_config_path()

            # Should fall back to default path
            assert config_path.parent == Path(".copinance") / "state" / "v2"
            assert config_path.name == "app.json"

    def test_get_config_path_creates_directory(self, temp_storage_path: Path) -> None:
        """Test that _get_config_path creates directory if it doesn't exist."""
        # Remove directory if it exists
        if temp_storage_path.exists():
            shutil.rmtree(temp_storage_path)

        # Patch create_storage to return storage with temp path
        with patch(
            "copinanceos.infrastructure.repositories.profile.current_profile.create_storage"
        ) as mock_create_storage:
            mock_create_storage.return_value = JsonFileStorage(base_path=temp_storage_path)
            config_path = _get_config_path()

            # Directory should be created
            assert temp_storage_path.exists()
            assert temp_storage_path.is_dir()
            assert config_path.parent == temp_storage_path / "state" / "v2"

    def test_set_current_profile_id_creates_file(self, config_file_path: Path) -> None:
        """Test that set_current_profile_id creates config file if it doesn't exist."""
        # Ensure file doesn't exist, but keep parent directory
        if config_file_path.exists():
            config_file_path.unlink()
        # Ensure parent directory exists (needed for file creation)
        config_file_path.parent.mkdir(parents=True, exist_ok=True)

        profile_id = uuid4()

        # Mock the config path
        with patch(
            "copinanceos.infrastructure.repositories.profile.current_profile._get_config_path"
        ) as mock_path:
            mock_path.return_value = config_file_path

            profile = CurrentProfile()
            profile.set_current_profile_id(profile_id)

            # File should be created
            assert config_file_path.exists()
            assert profile.get_current_profile_id() == profile_id

    def test_get_current_profile_id_handles_keyerror(self, config_file_path: Path) -> None:
        """Test that get_current_profile_id handles KeyError gracefully."""
        config_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write config that might cause KeyError in some edge cases
        # This tests the KeyError handling in the except clause
        config = {"schema_version": PERSISTENCE_SCHEMA_VERSION}
        config_file_path.write_text(json.dumps(config))

        # Mock the config path
        with patch(
            "copinanceos.infrastructure.repositories.profile.current_profile._get_config_path"
        ) as mock_path:
            mock_path.return_value = config_file_path

            profile = CurrentProfile()
            result = profile.get_current_profile_id()

            # Should return None, not raise KeyError
            assert result is None

    def test_set_current_profile_id_handles_valueerror_on_read(
        self, config_file_path: Path
    ) -> None:
        """Test that set_current_profile_id handles ValueError when reading config."""
        config_file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write invalid JSON that causes ValueError
        config_file_path.write_text("not valid json {")

        profile_id = uuid4()

        # Mock the config path
        with patch(
            "copinanceos.infrastructure.repositories.profile.current_profile._get_config_path"
        ) as mock_path:
            mock_path.return_value = config_file_path

            profile = CurrentProfile()
            # Should handle ValueError and create new config
            profile.set_current_profile_id(profile_id)

            # Should successfully set the profile ID
            assert profile.get_current_profile_id() == profile_id

    def test_integration_with_actual_storage(self, temp_storage_path: Path) -> None:
        """Test integration with actual storage without mocking."""
        profile_id = uuid4()

        # Patch create_storage to use temp path
        with patch(
            "copinanceos.infrastructure.repositories.profile.current_profile.create_storage"
        ) as mock_create_storage:
            mock_create_storage.return_value = JsonFileStorage(base_path=temp_storage_path)

            profile1 = CurrentProfile()
            profile1.set_current_profile_id(profile_id)

            # Create new instance to test persistence
            profile2 = CurrentProfile()
            retrieved_id = profile2.get_current_profile_id()

            assert retrieved_id == profile_id
            # Verify file was created
            config_file = temp_storage_path / "state" / "v2" / "app.json"
            assert config_file.exists()
