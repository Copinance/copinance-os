"""Current-profile state with explicit memory or file persistence."""

import json
from pathlib import Path
from uuid import UUID

from copinance_os.data.loaders.persistence import PERSISTENCE_SCHEMA_VERSION


class CurrentProfile:
    """Track the active profile without hidden filesystem access.

    With no ``config_path`` the state is process-local memory. Passing an
    explicit path enables lazy file persistence; the parent is created only
    when a value is written.
    """

    def __init__(self, config_path: Path | str | None = None) -> None:
        self._config_path = Path(config_path) if config_path is not None else None
        self._current_profile_id: UUID | None = None

    def get_current_profile_id(self) -> UUID | None:
        if self._config_path is None:
            return self._current_profile_id
        if not self._config_path.exists():
            return None
        try:
            with self._config_path.open(encoding="utf-8") as f:
                config = json.load(f)
            if config.get("schema_version") != PERSISTENCE_SCHEMA_VERSION:
                return None
            current_id = config.get("current_profile_id")
            return UUID(current_id) if current_id else None
        except (OSError, json.JSONDecodeError, ValueError, KeyError, TypeError):
            return None

    def set_current_profile_id(self, profile_id: UUID | None) -> None:
        if self._config_path is None:
            self._current_profile_id = profile_id
            return

        config: dict[str, object] = {}
        if self._config_path.exists():
            try:
                with self._config_path.open(encoding="utf-8") as f:
                    config = json.load(f)
            except (OSError, json.JSONDecodeError, ValueError, TypeError):
                config = {}

        if profile_id is None:
            config.pop("current_profile_id", None)
        else:
            config["current_profile_id"] = str(profile_id)
        config["schema_version"] = PERSISTENCE_SCHEMA_VERSION

        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        with self._config_path.open("w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
