"""Load ``PluginSpec`` lists from JSON or YAML config files (config-driven registration)."""

from __future__ import annotations

import json
from pathlib import Path
from types import ModuleType
from typing import Any

from copinance_os.domain.plugins.spec import PluginSpec

_yaml: ModuleType | None = None
try:
    import yaml as _yaml_mod

    _yaml = _yaml_mod
except ImportError:
    pass


def _normalize_plugin_root(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "plugins" in data:
        plugins = data["plugins"]
        if not isinstance(plugins, list):
            raise ValueError("'plugins' must be a list")
        return plugins
    raise ValueError("Plugin file must be a top-level list or an object with a 'plugins' list")


def load_plugin_specs_from_json(path: Path | str) -> list[PluginSpec]:
    """Parse a JSON file into ``PluginSpec`` instances.

    Accepts either:
    - a JSON array of plugin objects, or
    - an object with a ``\"plugins\"`` key containing that array.

    Raises:
        ValueError: If the structure is invalid.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    data: Any = json.loads(raw)
    items = _normalize_plugin_root(data)
    return [PluginSpec.model_validate(item) for item in items]


def load_plugin_specs_from_yaml(path: Path | str) -> list[PluginSpec]:
    """Parse a YAML file into ``PluginSpec`` instances (requires PyYAML)."""
    if _yaml is None:
        raise ImportError("YAML plugin configs require PyYAML. Install with: pip install pyyaml")

    p = Path(path)
    raw = p.read_text(encoding="utf-8")
    data: Any = _yaml.safe_load(raw)
    if data is None:
        return []
    items = _normalize_plugin_root(data)
    return [PluginSpec.model_validate(item) for item in items]
