"""Tool gating by tag — Phase 4 of the "faster, more reliable AI tool system"
design doc: "32 tools is past the point where selection accuracy degrades.
Expose a curated core set plus route-specific sets ... via ToolSpec.tags."

This is deliberately conservative on two axes:

1. **Safety default: unclassified tools are never excluded.** A tool this
   module doesn't recognize by name (a new builtin, a plugin, an app-owned
   tool registered via ``copinance_os.tool_bundles``) always stays in the
   list. Gating only narrows tools this module has *explicitly* classified —
   it must never silently drop a tool nobody has reviewed for gating.
2. **The tag-to-scope policy here is a first cut, not eval-backed.** It
   removes only the tools that are unambiguously irrelevant to a scope (fund
   ownership/portfolio tools for a broad market-wide question), not an
   aggressive curation. The doc's own Phase 4 also calls for "the TOON A/B
   [eval] that decides default-on" — the same eval-gated caution applies
   here: tightening this policy further should be driven by the
   tool-selection eval (``ai/llm/eval/tool_selection.py``) showing it
   actually improves selection accuracy, not by guessing.
"""

from __future__ import annotations

from copinance_os.domain.models.job import JobScope
from copinance_os.domain.ports.tools import Tool

# name -> tags. Only tools this module has reviewed appear here; anything
# else is left untagged (see module docstring point 1).
_DEFAULT_TAGS: dict[str, frozenset[str]] = {
    "get_current_date": frozenset({"core"}),
    "get_market_quote": frozenset({"market_data"}),
    "get_historical_market_data": frozenset({"market_data"}),
    "search_market_instruments": frozenset({"market_data"}),
    "get_options_chain": frozenset({"options"}),
    "get_options_positioning": frozenset({"options"}),
    "get_market_regime_indicators": frozenset({"regime"}),
    "get_macro_regime_indicators": frozenset({"regime"}),
    "get_sec_company_edgar_profile": frozenset({"sec_fundamentals"}),
    "get_sec_company_facts_statement": frozenset({"sec_fundamentals"}),
    "get_sec_compare_financials_metrics": frozenset({"sec_fundamentals"}),
    "get_sec_xbrl_statement_table": frozenset({"sec_fundamentals"}),
    "get_sec_13f_institutional_holdings": frozenset({"sec_ownership"}),
    "get_sec_insider_form4": frozenset({"sec_ownership"}),
    "get_sec_fund_entity": frozenset({"sec_funds"}),
    "get_sec_fund_filings": frozenset({"sec_funds"}),
    "get_sec_fund_latest_report": frozenset({"sec_funds"}),
    "get_sec_fund_portfolio": frozenset({"sec_funds"}),
    "find_sec_funds": frozenset({"sec_funds"}),
}


def default_tags_for(tool_name: str) -> frozenset[str]:
    """This module's tag classification for a tool, or empty if unclassified."""
    return _DEFAULT_TAGS.get(tool_name, frozenset())


def tags_for_job_scope(scope: JobScope) -> frozenset[str]:
    """Which tags are relevant for a job's scope.

    ``"core"`` is included for every scope — ``get_current_date`` is cheap,
    harmless, and useful regardless of what's being asked.
    """
    if scope == JobScope.MARKET:
        # A market-wide question ("how's the market doing") has no single
        # instrument to look up ownership or fund holdings for.
        return frozenset({"core", "market_data", "options", "regime", "sec_fundamentals"})
    return frozenset(
        {
            "core",
            "market_data",
            "options",
            "regime",
            "sec_fundamentals",
            "sec_ownership",
            "sec_funds",
        }
    )


def select_tools_by_tags(tools: list[Tool], wanted_tags: frozenset[str]) -> list[Tool]:
    """Filter ``tools`` to those tagged for ``wanted_tags`` — an unclassified
    tool (see ``default_tags_for``) always passes through untouched."""
    kept: list[Tool] = []
    for tool in tools:
        tags = default_tags_for(tool.get_name())
        if not tags or (tags & wanted_tags):
            kept.append(tool)
    return kept


def select_tools_for_job_scope(tools: list[Tool], scope: JobScope) -> list[Tool]:
    """Convenience: ``select_tools_by_tags`` using this module's scope policy."""
    return select_tools_by_tags(tools, tags_for_job_scope(scope))
