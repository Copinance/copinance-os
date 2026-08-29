"""Tool gating by tag: unclassified tools always pass through (safety default),
and the market-scope policy excludes only unambiguously irrelevant tool
families (fund ownership/portfolio tools) — see tool_gating.py's module
docstring for why this is a conservative first cut, not eval-tuned curation.
"""

from __future__ import annotations

from typing import Any

from copinance_os.core.pipeline.tools.tool_gating import (
    _DEFAULT_TAGS,
    default_tags_for,
    select_tools_by_tags,
    select_tools_for_job_scope,
    tags_for_job_scope,
)
from copinance_os.domain.models.job import JobScope
from copinance_os.domain.models.pipeline.tool_results import ToolResult
from copinance_os.domain.ports.tools import Tool, ToolSchema


class _NamedTool(Tool):
    def __init__(self, name: str) -> None:
        self._name = name

    def get_schema(self) -> ToolSchema:
        return ToolSchema(name=self._name, description=self._name, parameters={"type": "object"})

    def get_name(self) -> str:
        return self._name

    def get_description(self) -> str:
        return self._name

    async def execute(self, **kwargs: Any) -> ToolResult[Any]:
        return ToolResult(success=True, data=None)


def test_default_tags_for_known_tool() -> None:
    assert default_tags_for("get_market_quote") == frozenset({"market_data"})


def test_default_tags_for_unknown_tool_is_empty() -> None:
    assert default_tags_for("some_app_owned_tool") == frozenset()


def test_unclassified_tool_always_passes_through() -> None:
    """Safety default: a tool this module hasn't reviewed is never excluded,
    regardless of how narrow wanted_tags is."""
    tools: list[Tool] = [_NamedTool("get_signal_study")]  # app-owned, not in _DEFAULT_TAGS
    kept = select_tools_by_tags(tools, wanted_tags=frozenset({"market_data"}))
    assert kept == tools


def test_classified_tool_kept_when_tag_matches() -> None:
    tools: list[Tool] = [_NamedTool("get_market_quote")]
    kept = select_tools_by_tags(tools, wanted_tags=frozenset({"market_data"}))
    assert kept == tools


def test_classified_tool_dropped_when_tag_does_not_match() -> None:
    tools: list[Tool] = [_NamedTool("get_sec_fund_portfolio")]
    kept = select_tools_by_tags(tools, wanted_tags=frozenset({"market_data"}))
    assert kept == []


def test_market_scope_excludes_fund_and_ownership_tools() -> None:
    tools: list[Tool] = [
        _NamedTool("get_market_quote"),
        _NamedTool("get_sec_fund_portfolio"),
        _NamedTool("get_sec_13f_institutional_holdings"),
        _NamedTool("get_current_date"),
    ]
    kept = select_tools_for_job_scope(tools, JobScope.MARKET)
    kept_names = {t.get_name() for t in kept}
    assert kept_names == {"get_market_quote", "get_current_date"}


def test_instrument_scope_includes_fund_and_ownership_tools() -> None:
    tools: list[Tool] = [
        _NamedTool("get_sec_fund_portfolio"),
        _NamedTool("get_sec_13f_institutional_holdings"),
    ]
    kept = select_tools_for_job_scope(tools, JobScope.INSTRUMENT)
    assert {t.get_name() for t in kept} == {
        "get_sec_fund_portfolio",
        "get_sec_13f_institutional_holdings",
    }


def test_core_tag_present_for_every_scope() -> None:
    assert "core" in tags_for_job_scope(JobScope.MARKET)
    assert "core" in tags_for_job_scope(JobScope.INSTRUMENT)


def test_every_known_tool_name_has_at_least_one_tag() -> None:
    """A tool with an empty tag set is treated as unclassified (always
    included) rather than gated — an entry in _DEFAULT_TAGS with no tags
    would silently defeat its own classification."""
    for name, tags in _DEFAULT_TAGS.items():
        assert tags, f"{name} has an empty tag set"
