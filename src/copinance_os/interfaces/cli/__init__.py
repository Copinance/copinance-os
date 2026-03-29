"""Command-line interface for Copinance OS."""

from __future__ import annotations

from typing import Any

from copinance_os.interfaces.cli.main import main

__all__ = [
    "_root_cli_epilog_natural_language",
    "app",
    "main",
    "version_app",
]


def __getattr__(name: str) -> Any:
    """Lazy Typer/Rich root app so ``import copinance_os.interfaces.cli`` stays light."""
    if name == "app":
        from copinance_os.interfaces.cli.root import app as _app

        globals()["app"] = _app
        return _app
    if name == "version_app":
        from copinance_os.interfaces.cli.root import version_app as _version_app

        globals()["version_app"] = _version_app
        return _version_app
    if name == "_root_cli_epilog_natural_language":
        from copinance_os.interfaces.cli.root import (
            _root_cli_epilog_natural_language as _epilog,
        )

        globals()["_root_cli_epilog_natural_language"] = _epilog
        return _epilog
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
