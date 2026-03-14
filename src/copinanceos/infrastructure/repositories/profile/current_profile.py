"""Current profile state management - tracks which profile is active."""

import json
from pathlib import Path
from uuid import UUID

from copinanceos.infrastructure.persistence import PERSISTENCE_SCHEMA_VERSION, get_state_dir
from copinanceos.infrastructure.repositories.storage.factory import create_storage
from copinanceos.infrastructure.repositories.storage.file import JsonFileStorage


def _get_config_path() -> Path:
    """Get the path to the config file."""
    storage = create_storage()
    if isinstance(storage, JsonFileStorage):
        state_dir = get_state_dir(storage._root_path)
    else:
        state_dir = get_state_dir(Path(".copinance"))
    return state_dir / "app.json"


class CurrentProfile:
    """Manages the currently active profile state."""

    def get_current_profile_id(self) -> UUID | None:
        """Get the current profile ID.

        Returns:
            Current profile ID if set, None otherwise.
        """
        config_file = _get_config_path()
        if not config_file.exists():
            return None

        try:
            with open(config_file) as f:
                config = json.load(f)
                if config.get("schema_version") != PERSISTENCE_SCHEMA_VERSION:
                    return None
                current_id = config.get("current_profile_id")
                if current_id:
                    return UUID(current_id)
        except (json.JSONDecodeError, ValueError, KeyError):
            return None

        return None

    def set_current_profile_id(self, profile_id: UUID | None) -> None:
        """Set the current profile ID.

        Args:
            profile_id: Profile ID to set as current, or None to clear.
        """
        config_file = _get_config_path()
        config = {}
        if config_file.exists():
            try:
                with open(config_file) as f:
                    config = json.load(f)
            except (json.JSONDecodeError, ValueError):
                config = {}

        if profile_id is None:
            config.pop("current_profile_id", None)
        else:
            config["current_profile_id"] = str(profile_id)
        config["schema_version"] = PERSISTENCE_SCHEMA_VERSION

        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
