"""Eval harnesses — see tool_selection.py (tool-choice accuracy) and
format_ab.py (TOON vs. compact-JSON retrieval accuracy)."""

from copinance_os.ai.llm.eval.format_ab import (
    FormatAbCase,
    FormatAbReport,
    FormatAbResult,
    render_payload,
    run_format_ab_eval,
)
from copinance_os.ai.llm.eval.tool_selection import (
    ToolSelectionCase,
    ToolSelectionReport,
    ToolSelectionResult,
    run_tool_selection_eval,
)

__all__ = [
    "ToolSelectionCase",
    "ToolSelectionReport",
    "ToolSelectionResult",
    "run_tool_selection_eval",
    "FormatAbCase",
    "FormatAbReport",
    "FormatAbResult",
    "render_payload",
    "run_format_ab_eval",
]
