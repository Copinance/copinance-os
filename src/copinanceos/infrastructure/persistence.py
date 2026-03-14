"""Persistence path helpers and schema constants."""

from pathlib import Path

PERSISTENCE_SCHEMA_VERSION = "v2"


def get_persistence_root(base_path: Path | str = ".copinance") -> Path:
    """Return the root persistence directory."""
    root = Path(base_path)
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_data_dir(base_path: Path | str = ".copinance") -> Path:
    """Return the versioned entity storage directory."""
    path = get_persistence_root(base_path) / "data" / PERSISTENCE_SCHEMA_VERSION
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_cache_dir(base_path: Path | str = ".copinance") -> Path:
    """Return the versioned cache directory."""
    path = get_persistence_root(base_path) / "cache" / PERSISTENCE_SCHEMA_VERSION
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_results_dir(base_path: Path | str = ".copinance") -> Path:
    """Return the versioned workflow results directory."""
    path = get_persistence_root(base_path) / "results" / PERSISTENCE_SCHEMA_VERSION
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_state_dir(base_path: Path | str = ".copinance") -> Path:
    """Return the versioned application state directory."""
    path = get_persistence_root(base_path) / "state" / PERSISTENCE_SCHEMA_VERSION
    path.mkdir(parents=True, exist_ok=True)
    return path
