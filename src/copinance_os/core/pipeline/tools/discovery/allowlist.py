"""Stable question-driven tool name set for curated-question hints."""

from __future__ import annotations

from copinance_os.core.pipeline.tools.discovery import collect_question_driven_tools
from copinance_os.domain.models.pipeline.tool_bundle_context import ToolBundleContext


class _StubMarketProvider:
    def get_provider_name(self) -> str:
        return "stub_market"


class _StubFundamentalProvider:
    def get_provider_name(self) -> str:
        return "stub_fundamental"


def question_driven_tool_names() -> frozenset[str]:
    """Builtin question-driven tool names (no entry points / package scan)."""
    ctx = ToolBundleContext(
        market_data_provider=_StubMarketProvider(),  # type: ignore[arg-type]
        fundamental_data_provider=_StubFundamentalProvider(),  # type: ignore[arg-type]
    )
    tools = collect_question_driven_tools(
        ctx,
        load_entry_point_bundles=False,
        scan_bundles_package=None,
    )
    return frozenset(t.get_name() for t in tools)


def filter_suggested_tools(
    names: list[str] | None,
    allowed: frozenset[str],
) -> list[str] | None:
    """Drop unknown tool names; return None if input was None."""
    if names is None:
        return None
    filtered = [n for n in names if n in allowed]
    return filtered or None
