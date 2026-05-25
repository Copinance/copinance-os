"""Agent progress event schema."""

import pytest

from copinance_os.domain.models.pipeline.agent_progress import (
    RunStartedEvent,
    ToolStartedEvent,
    parse_agent_progress_event,
)


@pytest.mark.unit
def test_parse_run_started_roundtrip() -> None:
    ev = RunStartedEvent(
        run_id="r1",
        execution_type="question_driven_instrument_analysis",
        symbol="AAPL",
    )
    data = ev.model_dump(mode="json")
    out = parse_agent_progress_event(data)
    assert isinstance(out, RunStartedEvent)
    assert out.run_id == "r1"
    assert out.execution_type == "question_driven_instrument_analysis"


@pytest.mark.unit
def test_parse_tool_started() -> None:
    raw = {
        "schema_version": 1,
        "kind": "tool_started",
        "run_id": "x",
        "tool_name": "get_quote",
        "args_summary": '{"symbol": "AAPL"}',
        "iteration": 1,
        "call_index": 0,
    }
    out = parse_agent_progress_event(raw)
    assert isinstance(out, ToolStartedEvent)
    assert out.tool_name == "get_quote"
