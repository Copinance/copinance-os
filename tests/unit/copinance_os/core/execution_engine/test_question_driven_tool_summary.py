"""Tests for deterministic tool summaries when LLM synthesis is missing."""

import pytest

from copinance_os.core.execution_engine.question_driven_tool_summary import (
    build_partial_synthesis_message,
    is_tool_call_json_text,
    summarize_tool_calls_for_display,
)


@pytest.mark.unit
def test_is_tool_call_json_text() -> None:
    assert is_tool_call_json_text('{"tool": "get_sec_filings", "args": {"symbol": "X"}}')
    assert not is_tool_call_json_text("The revenue was up.")
    assert not is_tool_call_json_text('{"foo": 1}')


@pytest.mark.unit
def test_summarize_sec_filings_table() -> None:
    tool_calls = [
        {
            "tool": "get_sec_filings",
            "success": True,
            "response": [
                {
                    "filing_date": "2025-01-01",
                    "form": "10-K",
                    "accession_number": "000-00-0000001",
                }
            ],
        }
    ]
    out = summarize_tool_calls_for_display(tool_calls)
    assert "10-K" in out
    assert "000-00-0000001" in out


@pytest.mark.unit
def test_build_partial_includes_reason_and_table() -> None:
    msg = build_partial_synthesis_message(
        reason="LLM request failed after tools ran",
        error_detail="Server disconnected",
        tool_calls=[
            {
                "tool": "get_sec_filings",
                "success": True,
                "response": [{"filing_date": "x", "form": "10-K", "accession_number": "acc"}],
            }
        ],
    )
    assert "No model-written summary" in msg
    assert "Server disconnected" in msg
    assert "acc" in msg
