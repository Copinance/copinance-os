"""Tests for mapping executor payloads to ``AnalysisReport``."""

import pytest

from copinance_os.domain.services.instrument_analysis_report import (
    build_instrument_analysis_report,
)


@pytest.mark.unit
def test_build_instrument_analysis_report_maps_payload() -> None:
    payload = {
        "execution_type": "instrument_analysis",
        "execution_mode": "deterministic",
        "summary": {
            "text": "Instrument: TestCo\nCurrent Price: 10",
            "timeframe": "mid_term",
        },
        "analysis": {
            "symbol": "TEST",
            "timeframe": "mid_term",
            "metrics": {"valuation": {"pe_ratio": "12"}},
        },
    }
    report = build_instrument_analysis_report(payload)
    assert report is not None
    assert "TestCo" in report.summary
    assert report.key_metrics.get("symbol") == "TEST"
    assert report.key_metrics.get("metrics", {}).get("valuation", {}).get("pe_ratio") == "12"
    assert report.methodology
    assert report.assumptions
    assert report.limitations


@pytest.mark.unit
def test_build_instrument_analysis_report_non_instrument_returns_none() -> None:
    assert build_instrument_analysis_report({"execution_type": "macro_analysis"}) is None


@pytest.mark.unit
def test_build_instrument_analysis_report_multi_expiration() -> None:
    payload = {
        "execution_type": "instrument_analysis",
        "execution_mode": "deterministic",
        "multi_expiration": True,
        "expiration_dates_requested": ["2026-06-19", "2026-07-17"],
        "summary": {"text": "Combined", "timeframe": "short_term"},
        "expirations": [
            {
                "expiration_date": "2026-06-19",
                "analysis": {"metrics": {"underlying_price": "100"}},
            },
            {
                "expiration_date": "2026-07-17",
                "analysis": {"metrics": {"underlying_price": "101"}},
            },
        ],
    }
    report = build_instrument_analysis_report(payload)
    assert report is not None
    assert report.key_metrics.get("multi_expiration") is True
    assert len(report.key_metrics.get("expirations") or []) == 2
