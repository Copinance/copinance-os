"""CLI utility functions and decorators."""

import asyncio
import functools
import inspect
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, TypeVar

import structlog
from pydantic import BaseModel

from copinanceos.infrastructure.persistence import PERSISTENCE_SCHEMA_VERSION, get_results_dir

F = TypeVar("F", bound=Callable[..., Any])


def save_analysis_results(results: dict[str, Any], storage_path: str = ".copinance") -> Path | None:
    """Save analysis results to the versioned results directory as JSON.

    The results dict should contain execution_type, scope, market_type, and
    instrument_symbol or market_index (as set by executors) so the saved file
    is self-describing. Nested Pydantic models are serialized via _to_json_compatible.

    Returns:
        Path to the saved file, or None if results empty or save failed.
    """
    if not results:
        return None
    results_dir = get_results_dir(storage_path)

    execution_type = results.get("execution_type") or "analysis"
    instrument_symbol = results.get("instrument_symbol")
    market_index = results.get("market_index")
    market_type = results.get("market_type") or ("market" if market_index else "instrument")
    scope = results.get("scope")
    if scope is None and (instrument_symbol or market_index):
        scope = "market" if market_index and not instrument_symbol else "instrument"

    execution_ts = results.get("execution_timestamp")
    if isinstance(execution_ts, datetime):
        ts_str = execution_ts.strftime("%Y-%m-%dT%H-%M-%S")
    elif isinstance(execution_ts, str):
        ts_str = execution_ts.replace(":", "-").replace(".", "-").replace("+", "-")[:19]
    else:
        ts_str = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")

    symbol = instrument_symbol or market_index
    slug = f"{execution_type}_{symbol}_{ts_str}" if symbol else f"{execution_type}_{ts_str}"
    slug = re.sub(r"[^\w\-.]", "_", slug)
    target_dir = results_dir / execution_type / str(market_type)
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / f"{slug}.json"

    envelope = {
        "schema_version": PERSISTENCE_SCHEMA_VERSION,
        "saved_at": datetime.now(UTC).isoformat(),
        "execution_type": execution_type,
        "market_type": results.get("market_type"),
        "scope": scope if scope is not None else results.get("scope"),
        "target": {
            "instrument_symbol": instrument_symbol,
            "market_index": market_index,
        },
        "results": _to_json_compatible(results),
    }

    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(envelope, f, indent=2)
        return path
    except (OSError, TypeError) as e:
        structlog.get_logger(__name__).warning(
            "Failed to save analysis results", path=str(path), error=str(e)
        )
        return None


def _to_json_compatible(value: Any) -> Any:
    """Recursively normalize values for JSON persistence.

    Handles datetime, Decimal, Path, dict, list, and Pydantic BaseModel
    so analysis results (including nested models) are never lost on save.
    """
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, BaseModel):
        return _to_json_compatible(value.model_dump())
    if isinstance(value, dict):
        return {str(key): _to_json_compatible(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_json_compatible(item) for item in value]
    return value


def async_command(func: F) -> F:
    """Decorator to handle async CLI commands.

    This decorator wraps async CLI command functions and automatically
    runs them using asyncio.run(), eliminating the need for nested
    async functions and manual asyncio.run() calls.

    Usage:
        @analyze_app.command("market")
        @async_command
        async def analyze_equity(symbol: str):
            runner = container.job_runner()
            result = await runner.run(job, context)
            ...

    Args:
        func: Async function to wrap

    Returns:
        Synchronous wrapper function that runs the async function
    """
    if not inspect.iscoroutinefunction(func):
        raise TypeError(f"async_command decorator can only be used on async functions, got {func}")

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        """Synchronous wrapper that runs the async function."""
        return asyncio.run(func(*args, **kwargs))

    return wrapper  # type: ignore[return-value]
