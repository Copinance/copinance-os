"""Tests for RecordingProgressSink."""

import pytest

from copinance_os.core.progress.recording_sink import RecordingProgressSink
from copinance_os.domain.models.agent_progress import (
    LlmStreamProgressEvent,
    RunStartedEvent,
)


@pytest.mark.asyncio
async def test_recording_forwards_and_compacts_text_delta() -> None:
    inner_calls: list[object] = []

    class Inner:
        async def emit(self, event: object) -> None:
            inner_calls.append(event)

    inner = Inner()
    sink = RecordingProgressSink(inner)

    await sink.emit(
        RunStartedEvent(
            run_id="r1",
            execution_type="question_driven_instrument_analysis",
            symbol="LLY",
        )
    )
    await sink.emit(
        LlmStreamProgressEvent(
            run_id="r1",
            stream_kind="text_delta",
            text_delta="hello",
            native_streaming=True,
        )
    )

    assert len(sink.timeline) == 2
    assert sink.timeline[0]["kind"] == "run_started"
    assert sink.timeline[1]["kind"] == "llm_stream"
    assert sink.timeline[1]["text_delta"] == ""
    assert sink.timeline[1]["text_delta_chars"] == 5
    assert len(inner_calls) == 2
    assert inner_calls[1].text_delta == "hello"
