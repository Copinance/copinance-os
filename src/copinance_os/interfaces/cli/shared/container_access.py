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


def get_container() -> Container:
    from copinance_os.infra.di import container  # noqa: PLC0415 — lazy import; see module docstring

    return container
