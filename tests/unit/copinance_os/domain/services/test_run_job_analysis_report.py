"""Tests for report dispatch."""

import pytest

from copinance_os.domain.services.run_job_analysis_report import build_run_job_analysis_report


@pytest.mark.unit
def test_dispatch_instrument() -> None:
    r = build_run_job_analysis_report(
        {
            "execution_type": "instrument_analysis",
            "summary": {"text": "x"},
            "analysis": {"symbol": "A", "timeframe": "mid_term"},
        }
    )
    assert r is not None
    assert r.summary == "x"


@pytest.mark.unit
def test_dispatch_market() -> None:
    r = build_run_job_analysis_report(
        {
            "execution_type": "market_analysis",
            "market_index": "SPY",
            "market_regime_indicators": {"success": True},
            "macro_regime_indicators": {"success": True},
        }
    )
    assert r is not None
    assert "SPY" in r.summary


@pytest.mark.unit
def test_dispatch_unknown() -> None:
    assert build_run_job_analysis_report({"execution_type": "question_driven_analysis"}) is None
