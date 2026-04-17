"""Map deterministic market executor payloads to ``AnalysisReport``."""

from typing import Any

from copinance_os.data.literacy import instrument_analysis as ia_lit
from copinance_os.data.literacy import reports as reports_lit
from copinance_os.domain.literacy import resolve_financial_literacy
from copinance_os.domain.models.analysis_report import AnalysisReport
from copinance_os.domain.models.methodology import envelope_from_text_methodology
from copinance_os.domain.models.profile import FinancialLiteracy


def build_market_analysis_report(
    results: dict[str, Any], lit: FinancialLiteracy
) -> AnalysisReport | None:
    """Build a report envelope from ``market_analysis`` executor output, if applicable."""
    resolved_lit = resolve_financial_literacy(lit)
    if results.get("execution_type") != "market_analysis":
        return None

    idx = str(results.get("market_index") or "SPY")
    mri = results.get("market_regime_indicators")
    macro = results.get("macro_regime_indicators")
    mri_ok = isinstance(mri, dict) and bool(mri.get("success"))
    macro_ok = isinstance(macro, dict) and bool(macro.get("success"))

    summary = ia_lit.report_market_summary(idx, mri_ok, macro_ok, resolved_lit)

    key_metrics: dict[str, Any] = {
        "market_index": idx,
        "execution_mode": results.get("execution_mode"),
        "market_regime_indicators_success": mri.get("success") if isinstance(mri, dict) else None,
        "macro_regime_indicators_success": (
            macro.get("success") if isinstance(macro, dict) else None
        ),
    }

    methodology = envelope_from_text_methodology(
        spec_id="market_analysis.deterministic",
        model_family="regime_indicators_and_macro_series",
        assumptions=reports_lit.report_assumptions(resolved_lit),
        limitations=reports_lit.report_limitations(resolved_lit),
        data_inputs={
            "market_index": idx,
            "execution_mode": str(results.get("execution_mode") or ""),
        },
    )

    return AnalysisReport(
        summary=summary,
        key_metrics=key_metrics,
        methodology=methodology,
    )
