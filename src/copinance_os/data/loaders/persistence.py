"""Persistence path helpers and schema constants.

All persisted data (entity storage, cache, results, state) lives under a single
root directory. Default is .copinance so nothing is created at project root.
"""

from pathlib import Path

PERSISTENCE_SCHEMA_VERSION = "v2"

_DEFAULT_PERSISTENCE_ROOT = ".copinance"


def get_persistence_root(base_path: Path | str = ".copinance") -> Path:
    """Return the normalized root persistence path without creating it.

    Empty or "." is normalized to .copinance so data/cache/results/state
    are never created at project root.
    """
    raw = Path(base_path) if base_path else Path(_DEFAULT_PERSISTENCE_ROOT)
    if str(raw).strip() in ("", "."):
        # Keep all artifacts under a dedicated root to avoid polluting repo/project top level.
        raw = Path(_DEFAULT_PERSISTENCE_ROOT)
    return raw


def get_data_dir(base_path: Path | str = ".copinance") -> Path:
    """Return the versioned entity storage directory."""
    return get_persistence_root(base_path) / "data" / PERSISTENCE_SCHEMA_VERSION


def get_cache_dir(base_path: Path | str = ".copinance") -> Path:
    """Return the versioned cache directory."""
    return get_persistence_root(base_path) / "cache" / PERSISTENCE_SCHEMA_VERSION


def get_results_dir(base_path: Path | str = ".copinance") -> Path:
    """Return the versioned analysis results directory."""
    return get_persistence_root(base_path) / "results" / PERSISTENCE_SCHEMA_VERSION


def get_state_dir(base_path: Path | str = ".copinance") -> Path:
    """Return the versioned application state directory."""
    return get_persistence_root(base_path) / "state" / PERSISTENCE_SCHEMA_VERSION
