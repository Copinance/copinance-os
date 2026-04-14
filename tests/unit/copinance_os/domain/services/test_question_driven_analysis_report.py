"""Tests for question-driven analysis report envelope."""

import pytest

from copinance_os.domain.models.profile import FinancialLiteracy
from copinance_os.domain.services.question_driven_analysis_report import (
    build_question_driven_analysis_report,
)


@pytest.mark.unit
def test_wrong_execution_type_returns_none() -> None:
    assert (
        build_question_driven_analysis_report(
            {"execution_type": "instrument_analysis"}, FinancialLiteracy.INTERMEDIATE
        )
        is None
    )


@pytest.mark.unit
def test_success_envelope() -> None:
    r = build_question_driven_analysis_report(
        {
            "execution_type": "question_driven_analysis",
            "analysis": "Narrative.",
            "status": "completed",
            "iterations": 1,
            "tools_used": ["a"],
            "tool_calls": [{"tool": "a"}],
        },
        FinancialLiteracy.INTERMEDIATE,
    )
    assert r is not None
    assert r.summary == "Narrative."
    assert r.key_metrics.get("iterations") == 1


@pytest.mark.unit
def test_partial_synthesis_adds_limitation() -> None:
    r = build_question_driven_analysis_report(
        {
            "execution_type": "question_driven_analysis",
            "analysis": "Fallback text",
            "status": "completed",
            "synthesis_status": "partial",
            "tool_calls": [],
        },
        FinancialLiteracy.INTERMEDIATE,
    )
    assert r is not None
    assert r.key_metrics.get("synthesis_status") == "partial"
    lims = tuple(lim for spec in r.methodology.specs for lim in spec.limitations)
    assert any("LLM narrative" in lim for lim in lims)
