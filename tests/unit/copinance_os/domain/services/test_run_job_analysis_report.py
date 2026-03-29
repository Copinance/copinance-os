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
def test_dispatch_question_driven() -> None:
    r = build_run_job_analysis_report(
        {
            "execution_type": "question_driven_analysis",
            "analysis": "Summary of findings.",
            "status": "completed",
            "iterations": 2,
            "tools_used": ["get_quote"],
            "tool_calls": [{"tool": "get_quote"}],
            "llm_provider": "test",
            "llm_model": "test-model",
            "numeric_grounding_policy": "policy text",
        }
    )
    assert r is not None
    assert "findings" in r.summary
    assert r.key_metrics.get("tool_calls_count") == 1


@pytest.mark.unit
def test_dispatch_question_driven_failed() -> None:
    r = build_run_job_analysis_report(
        {
            "execution_type": "question_driven_analysis",
            "status": "failed",
            "error": "LLM analyzer not configured",
            "message": "LLM analyzer is required for question-driven analysis",
        }
    )
    assert r is not None
    assert "required" in r.summary.lower() or "LLM" in r.summary


@pytest.mark.unit
def test_dispatch_unknown_executor_type() -> None:
    assert build_run_job_analysis_report({"execution_type": "future_executor"}) is None
