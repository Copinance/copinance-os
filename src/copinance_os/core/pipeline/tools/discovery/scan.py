"""Filesystem-style discovery: import submodules and collect ``tool_bundle_factory``."""

from __future__ import annotations

import importlib
import pkgutil

from copinance_os.domain.ports.tool_bundles import ToolBundleFactory

TOOL_BUNDLE_FACTORY_ATTR = "tool_bundle_factory"


def scan_tool_bundle_factories(package_name: str) -> list[ToolBundleFactory]:
    """Import submodules under *package_name* and collect ``tool_bundle_factory`` callables.

    Each submodule may define::

        def tool_bundle_factory(ctx: ToolBundleContext) -> list[Tool]: ...

    The package must exist (create an ``__init__.py`` even if empty).
    """
    pkg = importlib.import_module(package_name)
    path = getattr(pkg, "__path__", None)
    if path is None:
        return []
    out: list[ToolBundleFactory] = []
    prefix = f"{pkg.__name__}."
    for _finder, mod_name, _ispkg in pkgutil.walk_packages(path, prefix):
        mod = importlib.import_module(mod_name)
        factory = getattr(mod, TOOL_BUNDLE_FACTORY_ATTR, None)
        if callable(factory):
            out.append(factory)
    return out
