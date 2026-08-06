"""Lazy access to the DI container for CLI modules.

Importing ``copinance_os.infra.di`` executes ``container.py``, which pulls in data
providers (yfinance, QuantLib, EDGAR, …), use-case wiring, and orchestration.
CLI packages should import this module (light) and call ``get_container()`` inside
command handlers so ``copinance <group> --help`` and Typer startup stay fast.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from copinance_os.infra.di.container import Container

_cli_container: Container | None = None


def get_container() -> Container:
    """Return the explicitly stateful CLI container."""
    global _cli_container
    if _cli_container is not None:
        return _cli_container

    from datetime import timedelta  # noqa: PLC0415

    from copinance_os.data.cache import CacheManager, LocalFileCacheBackend  # noqa: PLC0415
    from copinance_os.data.loaders.persistence import get_cache_dir, get_state_dir  # noqa: PLC0415
    from copinance_os.infra.config import get_settings, get_storage_path_safe  # noqa: PLC0415
    from copinance_os.infra.di import create_container  # noqa: PLC0415

    settings = get_settings()
    storage_path = get_storage_path_safe()
    cache_manager = (
        CacheManager(
            backend=LocalFileCacheBackend(get_cache_dir(storage_path)),
            default_ttl=timedelta(hours=1),
        )
        if settings.cache_enabled
        else CacheManager()
    )
    profile_path = (
        str(get_state_dir(storage_path) / "app.json") if settings.storage_type == "file" else None
    )
    _cli_container = create_container(
        load_from_env=True,
        cache_manager=cache_manager,
        storage_type=settings.storage_type,
        storage_path=storage_path if settings.storage_type == "file" else None,
        current_profile_path=profile_path,
    )

    return _cli_container
