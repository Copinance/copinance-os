"""Map instrument executor payloads to ``AnalysisReport`` (domain envelope)."""

from typing import Any

from copinance_os.domain.models.analysis_report import AnalysisReport

_DEFAULT_METHODOLOGY = (
    "Deterministic instrument analysis: quote, historical price statistics, "
    "and fundamentals-derived ratios when available."
)
_DEFAULT_ASSUMPTIONS = (
    "Market data may be delayed or incomplete; provider-dependent.",
    "Ratios use latest reported fundamentals within the pipeline window.",
)
_DEFAULT_LIMITATIONS = (
    "Not investment advice; for research and education only.",
    "Does not model transaction costs, taxes, or liquidity.",
)


def build_instrument_analysis_report(results: dict[str, Any]) -> AnalysisReport | None:
    """Build a report envelope from ``instrument_analysis`` executor output, if applicable."""
    if results.get("execution_type") != "instrument_analysis":
        return None

    summary_block = results.get("summary")
    summary_text = ""
    if isinstance(summary_block, dict) and summary_block.get("text"):
        summary_text = str(summary_block["text"])
    elif isinstance(summary_block, str):
        summary_text = summary_block

    key_metrics: dict[str, Any] = {"execution_mode": results.get("execution_mode")}
    analysis = results.get("analysis")
    if isinstance(analysis, dict):
        key_metrics["symbol"] = analysis.get("symbol")
        key_metrics["timeframe"] = analysis.get("timeframe")
        metrics = analysis.get("metrics")
        if metrics:
            key_metrics["metrics"] = metrics

    return AnalysisReport(
        summary=summary_text or "Instrument analysis completed.",
        key_metrics=key_metrics,
        methodology=_DEFAULT_METHODOLOGY,
        assumptions=list(_DEFAULT_ASSUMPTIONS),
        limitations=list(_DEFAULT_LIMITATIONS),
    )
