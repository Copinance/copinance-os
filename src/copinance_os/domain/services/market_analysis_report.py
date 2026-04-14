"""Map deterministic market executor payloads to ``AnalysisReport``."""

from typing import Any

from copinance_os.domain.models.analysis_report import AnalysisReport
from copinance_os.domain.models.methodology import envelope_from_text_methodology

_DEFAULT_ASSUMPTIONS = (
    "Macro and market series may be delayed; provider availability affects coverage.",
    "Regime labels are model outputs, not forecasts.",
)
_DEFAULT_LIMITATIONS = (
    "Not investment advice; for research and education only.",
    "Does not include transaction costs, slippage, or portfolio constraints.",
)


def build_market_analysis_report(results: dict[str, Any]) -> AnalysisReport | None:
    """Build a report envelope from ``market_analysis`` executor output, if applicable."""
    if results.get("execution_type") != "market_analysis":
        return None

    idx = str(results.get("market_index") or "SPY")
    mri = results.get("market_regime_indicators")
    macro = results.get("macro_regime_indicators")
    mri_ok = isinstance(mri, dict) and bool(mri.get("success"))
    macro_ok = isinstance(macro, dict) and bool(macro.get("success"))

    summary = (
        f"Deterministic market and macro regime snapshot for {idx}. "
        f"Market indicators: {'ok' if mri_ok else 'incomplete'}; "
        f"macro block: {'ok' if macro_ok else 'incomplete'}."
    )

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
        assumptions=_DEFAULT_ASSUMPTIONS,
        limitations=_DEFAULT_LIMITATIONS,
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
