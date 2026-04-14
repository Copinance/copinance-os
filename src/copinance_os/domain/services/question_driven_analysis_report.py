"""Map question-driven executor payloads to ``AnalysisReport`` (rule 14 envelope)."""

from __future__ import annotations

from typing import Any

from copinance_os.domain.models.analysis_report import AnalysisReport
from copinance_os.domain.models.methodology import envelope_from_text_methodology

_DEFAULT_ASSUMPTIONS: tuple[str, ...] = (
    "External data may be delayed or incomplete; tool availability depends on configuration.",
    "Model output is explanatory; figures are provisional unless matched to tool results.",
)
_DEFAULT_LIMITATIONS: tuple[str, ...] = (
    "Not investment advice; for research and education only.",
    "LLM narrative is not a source of truth for prices, returns, Greeks, or ratios.",
)


def build_question_driven_analysis_report(results: dict[str, Any]) -> AnalysisReport | None:
    """Build a report envelope from ``question_driven_analysis`` executor output, if applicable."""
    if results.get("execution_type") != "question_driven_analysis":
        return None

    status = results.get("status")
    err = results.get("error")
    msg = results.get("message")
    analysis = results.get("analysis")

    if status == "failed" or err:
        summary = str(msg or err or "Question-driven analysis did not complete.")
        key_metrics: dict[str, Any] = {
            "status": status or "failed",
            "execution_mode": results.get("execution_mode"),
            "instrument_symbol": results.get("instrument_symbol"),
            "market_index": results.get("market_index"),
        }
        if err:
            key_metrics["error"] = str(err)
        methodology = envelope_from_text_methodology(
            spec_id="question_driven_analysis.aborted",
            model_family="llm_tool_loop",
            assumptions=_DEFAULT_ASSUMPTIONS,
            limitations=_DEFAULT_LIMITATIONS,
            data_inputs={"status": "failed"},
        )
        return AnalysisReport(
            summary=summary,
            key_metrics=key_metrics,
            methodology=methodology,
        )

    summary_text = ""
    if isinstance(analysis, str):
        summary_text = analysis.strip()[:8000]
    elif analysis is not None:
        summary_text = str(analysis)[:8000]

    if not summary_text:
        summary_text = str(msg or "Question-driven analysis completed.")

    policy = results.get("numeric_grounding_policy")
    key_metrics = {
        "execution_mode": results.get("execution_mode"),
        "instrument_symbol": results.get("instrument_symbol"),
        "market_index": results.get("market_index"),
        "timeframe": results.get("timeframe"),
        "iterations": results.get("iterations"),
        "llm_provider": results.get("llm_provider"),
        "llm_model": results.get("llm_model"),
        "tools_used_count": len(results.get("tools_used") or []),
        "tool_calls_count": len(results.get("tool_calls") or []),
    }
    if policy:
        key_metrics["numeric_grounding_policy"] = policy
    if results.get("llm_usage"):
        key_metrics["llm_usage"] = results["llm_usage"]
    if results.get("synthesis_status"):
        key_metrics["synthesis_status"] = results["synthesis_status"]
    if results.get("llm_synthesis_error"):
        key_metrics["llm_synthesis_error"] = str(results["llm_synthesis_error"])[:2000]

    assumptions = _DEFAULT_ASSUMPTIONS
    if policy:
        assumptions = (*_DEFAULT_ASSUMPTIONS, str(policy))

    limitations = _DEFAULT_LIMITATIONS
    if results.get("synthesis_status") == "partial":
        limitations = (
            *_DEFAULT_LIMITATIONS,
            "Final LLM narrative was not available; summary below includes tool output formatted for display.",
        )

    methodology = envelope_from_text_methodology(
        spec_id="question_driven_analysis.llm_tools",
        model_family="llm_tool_loop",
        assumptions=assumptions,
        limitations=limitations,
        data_inputs={
            "execution_mode": str(results.get("execution_mode") or ""),
            "llm_model": str(results.get("llm_model") or ""),
        },
    )

    return AnalysisReport(
        summary=summary_text,
        key_metrics=key_metrics,
        methodology=methodology,
    )
