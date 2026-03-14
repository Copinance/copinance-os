"""Cache management CLI commands."""

import asyncio
import shutil
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from copinanceos.infrastructure.config import get_settings
from copinanceos.infrastructure.containers import container
from copinanceos.infrastructure.persistence import (
    PERSISTENCE_SCHEMA_VERSION,
    get_data_dir,
)

cache_app = typer.Typer(help="Cache management commands")
console = Console()


def _clear_stored_instruments() -> bool:
    """Remove stored instrument/market data (e.g. equities list). Returns True if removed."""
    storage_path = Path(get_settings().storage_path)
    market_dir = get_data_dir(storage_path) / "market"
    if market_dir.exists():
        shutil.rmtree(market_dir)
        return True
    return False


@cache_app.command("clear")
def clear_cache(
    tool_name: str | None = typer.Option(None, "--tool", help="Clear cache for specific tool only"),
) -> None:
    """Clear cached tool data and stored instrument list.

    Clears:
    - Tool result cache (e.g. quotes, historical data) under .copinance/cache/
    - Stored instrument/market data (e.g. equities list) under .copinance/data/

    Does not clear profiles or workflow results.
    """

    async def _clear() -> None:
        cache_manager = container.cache_manager()
        deleted_count = await cache_manager.clear(tool_name)
        cleared_instruments = _clear_stored_instruments()

        parts = []
        if tool_name:
            parts.append(f"{deleted_count} cache entries for tool: {tool_name}")
        else:
            parts.append(f"{deleted_count} tool cache entries")
        if cleared_instruments:
            parts.append("stored instrument data")
        console.print(
            "✓ Cleared " + " and ".join(parts),
            style="bold green",
        )

    asyncio.run(_clear())


@cache_app.command("refresh")
def refresh_cache(
    tool_name: str = typer.Argument(..., help="Tool name to refresh"),
    args: list[str] = typer.Option(
        [],
        "--arg",
        help="Cache parameter in key=value form. Repeat for multiple parameters.",
    ),
) -> None:
    """Refresh cached data for a specific tool call.

    This deletes the cache entry, forcing the next call to fetch fresh data.
    """

    async def _refresh() -> None:
        cache_manager = container.cache_manager()

        params: dict[str, Any] = {}
        for arg in args:
            if "=" not in arg:
                console.print(
                    f"Invalid --arg value: {arg}. Expected key=value format.",
                    style="bold red",
                )
                return
            key, value = arg.split("=", 1)
            params[key] = value

        deleted = await cache_manager.delete(tool_name, **params)
        params_suffix = f" ({', '.join(f'{k}={v}' for k, v in params.items())})" if params else ""
        if deleted:
            console.print(
                f"✓ Refreshed cache for {tool_name}{params_suffix}",
                style="bold green",
            )
        else:
            console.print(
                f"⚠ No cache entry found for {tool_name}{params_suffix}",
                style="bold yellow",
            )

    asyncio.run(_refresh())


@cache_app.command("info")
def cache_info() -> None:
    """Show cache information."""

    async def _info() -> None:
        cache_manager = container.cache_manager()
        backend = cache_manager.get_backend()

        table = Table(title="Cache Information")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Backend", backend.get_backend_name())
        table.add_row("Tool cache directory", str(getattr(backend, "_cache_dir", "N/A")))
        storage_path = Path(get_settings().storage_path)
        table.add_row(
            "Stored data directory",
            str(get_data_dir(storage_path)) + " (instrument list etc.)",
        )
        table.add_row("Schema Version", PERSISTENCE_SCHEMA_VERSION)

        console.print(table)

    asyncio.run(_info())
