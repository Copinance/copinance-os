"""Tests for explicit current-profile state backends."""

import json
from pathlib import Path
from uuid import uuid4

import pytest

from copinance_os.data.loaders.persistence import PERSISTENCE_SCHEMA_VERSION
from copinance_os.data.repositories.profile.current_profile import CurrentProfile


@pytest.mark.unit
class TestCurrentProfile:
    def test_default_is_memory_only(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)
        profile_id = uuid4()
        profile = CurrentProfile()

        profile.set_current_profile_id(profile_id)

        assert profile.get_current_profile_id() == profile_id
        assert list(tmp_path.iterdir()) == []

    def test_memory_state_is_instance_local(self) -> None:
        first = CurrentProfile()
        first.set_current_profile_id(uuid4())

        assert CurrentProfile().get_current_profile_id() is None

    def test_file_state_is_lazy(self, tmp_path: Path) -> None:
        config_path = tmp_path / "missing" / "state" / "app.json"
        profile = CurrentProfile(config_path)

        assert profile.get_current_profile_id() is None
        assert not config_path.parent.exists()

    def test_explicit_file_state_round_trip(self, tmp_path: Path) -> None:
        config_path = tmp_path / "state" / "app.json"
        profile_id = uuid4()

        CurrentProfile(config_path).set_current_profile_id(profile_id)

        assert CurrentProfile(config_path).get_current_profile_id() == profile_id
        data = json.loads(config_path.read_text())
        assert data["schema_version"] == PERSISTENCE_SCHEMA_VERSION

    def test_clear_file_state_preserves_other_keys(self, tmp_path: Path) -> None:
        config_path = tmp_path / "state" / "app.json"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            json.dumps(
                {
                    "schema_version": PERSISTENCE_SCHEMA_VERSION,
                    "current_profile_id": str(uuid4()),
                    "other": "value",
                }
            )
        )

        CurrentProfile(config_path).set_current_profile_id(None)

        data = json.loads(config_path.read_text())
        assert "current_profile_id" not in data
        assert data["other"] == "value"

    @pytest.mark.parametrize(
        "content",
        ["not-json", "{}", '{"schema_version":"old"}', '{"current_profile_id":"bad"}'],
    )
    def test_invalid_file_state_is_a_miss(self, tmp_path: Path, content: str) -> None:
        config_path = tmp_path / "app.json"
        config_path.write_text(content)

        assert CurrentProfile(config_path).get_current_profile_id() is None
