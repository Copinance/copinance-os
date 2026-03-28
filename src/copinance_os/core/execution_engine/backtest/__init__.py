"""Backtest and simulation entrypoints (orchestrated execution; domain remains pure)."""

from copinance_os.core.execution_engine.backtest.simple_long_only_runner import (
    execute_simple_long_only_backtest,
)

__all__ = ["execute_simple_long_only_backtest"]
