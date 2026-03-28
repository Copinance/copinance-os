"""In-memory plugin registry (config wires callables; domain stays import-light)."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any, Generic, TypeVar, cast

from copinance_os.domain.plugins.spec import PluginSpec

T = TypeVar("T")


class PluginRegistry(Generic[T]):
    """Name → factory or instance registry for indicators, strategies, or tools."""

    def __init__(self) -> None:
        self._entries: dict[str, T] = {}

    def register(self, name: str, plugin: T, *, overwrite: bool = False) -> None:
        if not name or not str(name).strip():
            raise ValueError("plugin name is required")
        key = str(name).strip()
        if key in self._entries and not overwrite:
            raise KeyError(f"plugin already registered: {key}")
        self._entries[key] = plugin

    def get(self, name: str) -> T:
        key = str(name).strip()
        if key not in self._entries:
            raise KeyError(f"unknown plugin: {key}")
        return self._entries[key]

    def try_get(self, name: str) -> T | None:
        return self._entries.get(str(name).strip())

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries.keys()))

    def clear(self) -> None:
        self._entries.clear()


def resolve_plugin_callable(spec: Any) -> Callable[..., Any]:
    """Import ``spec.import_path`` and return ``spec.qualified_name`` callable."""
    if not isinstance(spec, PluginSpec):
        spec = PluginSpec.model_validate(spec)
    module = importlib.import_module(spec.import_path)
    target = getattr(module, spec.qualified_name, None)
    if target is None:
        raise ImportError(f"{spec.qualified_name!r} not found in {spec.import_path}")
    if not callable(target):
        raise TypeError(f"{spec.import_path}.{spec.qualified_name} is not callable")
    return cast(Callable[..., Any], target)
