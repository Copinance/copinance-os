"""Protocol for configurable tool bundle factories."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from copinance_os.domain.ports.tools import Tool

if TYPE_CHECKING:
    from copinance_os.domain.models.tool_bundle_context import ToolBundleContext


class ToolBundleFactory(Protocol):
    """Callable that builds zero or more tools from injected dependencies."""

    def __call__(self, ctx: ToolBundleContext) -> list[Tool]:
        """Return tools for this bundle (may be empty if deps are absent)."""
        ...
