"""Tests for market ``AnalysisReport`` mapping."""

import pytest

from copinance_os.domain.services.market_analysis_report import build_market_analysis_report


@pytest.mark.unit
def test_build_market_analysis_report() -> None:
    payload = {
        "execution_type": "market_analysis",
        "market_index": "QQQ",
        "execution_mode": "deterministic",
        "market_regime_indicators": {"success": True},
        "macro_regime_indicators": {"success": False},
    }
    r = build_market_analysis_report(payload)
    assert r is not None
    assert "QQQ" in r.summary
    assert r.key_metrics.get("market_regime_indicators_success") is True


@pytest.mark.unit
def test_build_market_analysis_report_wrong_type() -> None:
    assert build_market_analysis_report({"execution_type": "instrument_analysis"}) is None
