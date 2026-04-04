"""Progress sink that records a compact timeline for integrator UIs (REST/SSE summaries)."""

from __future__ import annotations

from typing import Any

from copinance_os.core.progress.emit import maybe_emit_progress
from copinance_os.domain.models.agent_progress import AgentProgressEvent, LlmStreamProgressEvent
from copinance_os.domain.ports.progress import ProgressSink


class RecordingProgressSink:
    """Forwards to an optional inner sink and appends JSON-ready dicts to ``timeline``.

    ``llm_stream`` events with ``stream_kind=text_delta`` omit token text; ``text_delta_chars``
    holds the character count so clients can show streaming activity without huge payloads.
    """

    def __init__(self, inner: ProgressSink | None) -> None:
        self._inner = inner
        self.timeline: list[dict[str, Any]] = []

    def _to_timeline_row(self, event: AgentProgressEvent) -> dict[str, Any]:
        if isinstance(event, LlmStreamProgressEvent) and event.stream_kind == "text_delta":
            n = len(event.text_delta or "")
            return {
                **event.model_dump(),
                "text_delta": "",
                "text_delta_chars": n,
            }
        return event.model_dump()

    async def emit(self, event: AgentProgressEvent) -> None:
        self.timeline.append(self._to_timeline_row(event))
        await maybe_emit_progress(self._inner, event)
