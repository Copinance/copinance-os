"""CLI utility functions and decorators."""

import asyncio
import functools
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar

import structlog

F = TypeVar("F", bound=Callable[..., Any])


def save_workflow_results(results: dict[str, Any], storage_path: str = ".copinance") -> Path | None:
    """Save workflow results to .copinance/results/ as JSON.

    Args:
        results: The results dict from RunWorkflowResponse (must be JSON-serializable).
        storage_path: Base path for storage (default .copinance).

    Returns:
        Path to the saved file, or None if results empty or save failed.
    """
    if not results:
        return None
    base = Path(storage_path)
    results_dir = base / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    workflow_type = results.get("workflow_type") or "workflow"
    execution_ts = results.get("execution_timestamp")
    if isinstance(execution_ts, datetime):
        ts_str = execution_ts.strftime("%Y-%m-%dT%H-%M-%S")
    elif isinstance(execution_ts, str):
        ts_str = execution_ts.replace(":", "-").replace(".", "-").replace("+", "-")[:19]
    else:
        ts_str = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%S")

    symbol = results.get("stock_symbol") or results.get("market_index")
    if symbol:
        slug = f"{workflow_type}_{symbol}_{ts_str}"
    else:
        slug = f"{workflow_type}_{ts_str}"
    slug = re.sub(r"[^\w\-.]", "_", slug)
    path = results_dir / f"{slug}.json"

    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
        return path
    except (OSError, TypeError) as e:
        structlog.get_logger(__name__).warning(
            "Failed to save workflow results", path=str(path), error=str(e)
        )
        return None


def async_command(func: F) -> F:
    """Decorator to handle async CLI commands.

    This decorator wraps async CLI command functions and automatically
    runs them using asyncio.run(), eliminating the need for nested
    async functions and manual asyncio.run() calls.

    Usage:
        @analyze_app.command("stock")
        @async_command
        async def analyze_stock(symbol: str):
            # Async code here
            response = await use_case.execute(request)
            ...

    Args:
        func: Async function to wrap

    Returns:
        Synchronous wrapper function that runs the async function
    """
    if not asyncio.iscoroutinefunction(func):
        raise TypeError(f"async_command decorator can only be used on async functions, got {func}")

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        """Synchronous wrapper that runs the async function."""
        return asyncio.run(func(*args, **kwargs))

    return wrapper  # type: ignore[return-value]
