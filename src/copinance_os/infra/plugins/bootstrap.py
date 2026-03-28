"""Build a ``PluginRegistry`` of resolved callables from config files or in-memory specs."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from copinance_os.domain.plugins.registry import PluginRegistry, resolve_plugin_callable
from copinance_os.domain.plugins.spec import PluginSpec
from copinance_os.infra.plugins.load_specs import (
    load_plugin_specs_from_json,
    load_plugin_specs_from_yaml,
)


def build_callable_registry_from_specs(
    specs: Iterable[PluginSpec],
    *,
    overwrite: bool = False,
) -> PluginRegistry[Callable[..., Any]]:
    """Resolve each spec to a callable and register under ``spec.name``."""
    reg: PluginRegistry[Callable[..., Any]] = PluginRegistry()
    for spec in specs:
        fn = resolve_plugin_callable(spec)
        reg.register(spec.name, fn, overwrite=overwrite)
    return reg


def build_callable_registry_from_json(
    path: Path | str,
    *,
    overwrite: bool = False,
) -> PluginRegistry[Callable[..., Any]]:
    """Load JSON plugin list and build a callable registry."""
    return build_callable_registry_from_specs(
        load_plugin_specs_from_json(path),
        overwrite=overwrite,
    )


def build_callable_registry_from_yaml(
    path: Path | str,
    *,
    overwrite: bool = False,
) -> PluginRegistry[Callable[..., Any]]:
    """Load YAML plugin list (requires PyYAML) and build a callable registry."""
    return build_callable_registry_from_specs(
        load_plugin_specs_from_yaml(path),
        overwrite=overwrite,
    )
