"""Dispatch executor payloads to the appropriate ``AnalysisReport`` builder."""

from typing import Any

from copinance_os.domain.models.analysis_report import AnalysisReport
from copinance_os.domain.models.profile import FinancialLiteracy
from copinance_os.domain.services.instrument_analysis_report import (
    build_instrument_analysis_report,
)
from copinance_os.domain.services.market_analysis_report import build_market_analysis_report
from copinance_os.domain.services.question_driven_analysis_report import (
    build_question_driven_analysis_report,
)


def build_run_job_analysis_report(
    results: dict[str, Any], lit: FinancialLiteracy
) -> AnalysisReport | None:
    """Return a structured report when the executor type has a registered envelope."""
    et = results.get("execution_type")
    if et == "instrument_analysis":
        return build_instrument_analysis_report(results, lit)
    if et == "market_analysis":
        return build_market_analysis_report(results, lit)
    if et == "question_driven_analysis":
        return build_question_driven_analysis_report(results, lit)
    return None
