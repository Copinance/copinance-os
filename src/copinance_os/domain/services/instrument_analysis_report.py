"""Map instrument executor payloads to ``AnalysisReport`` (domain envelope)."""

from typing import Any

from copinance_os.data.literacy import instrument_analysis as ia_lit
from copinance_os.data.literacy import reports as reports_lit
from copinance_os.domain.literacy import resolve_financial_literacy
from copinance_os.domain.models.analysis_report import AnalysisReport
from copinance_os.domain.models.methodology import envelope_from_text_methodology
from copinance_os.domain.models.profile import FinancialLiteracy


def build_instrument_analysis_report(
    results: dict[str, Any], lit: FinancialLiteracy
) -> AnalysisReport | None:
    """Build a report envelope from ``instrument_analysis`` executor output, if applicable."""
    resolved_lit = resolve_financial_literacy(lit)
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
    if results.get("multi_expiration"):
        key_metrics["multi_expiration"] = True
        if results.get("expiration_dates_requested"):
            key_metrics["expiration_dates_requested"] = results["expiration_dates_requested"]
        expirations = results.get("expirations")
        if isinstance(expirations, list):
            key_metrics["expirations"] = [
                {
                    "expiration_date": block.get("expiration_date"),
                    "metrics": (block.get("analysis") or {}).get("metrics"),
                }
                for block in expirations
                if isinstance(block, dict)
            ]
    elif isinstance(analysis, dict):
        key_metrics["symbol"] = analysis.get("symbol")
        key_metrics["timeframe"] = analysis.get("timeframe")
        metrics = analysis.get("metrics")
        if metrics:
            key_metrics["metrics"] = metrics

    methodology = envelope_from_text_methodology(
        spec_id="instrument_analysis.deterministic",
        model_family="deterministic_quote_fundamentals_pipeline",
        assumptions=reports_lit.report_assumptions(resolved_lit),
        limitations=reports_lit.report_limitations(resolved_lit),
        data_inputs={"execution_mode": str(results.get("execution_mode") or "")},
    )

    return AnalysisReport(
        summary=summary_text or ia_lit.report_instrument_default_summary(resolved_lit),
        key_metrics=key_metrics,
        methodology=methodology,
    )
