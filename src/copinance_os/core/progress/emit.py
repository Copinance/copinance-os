"""Optional progress emission (no-op when sink is absent)."""

from __future__ import annotations

from copinance_os.domain.models.pipeline.agent_progress import AgentProgressEvent
from copinance_os.domain.ports.progress import ProgressSink


async def maybe_emit_progress(sink: ProgressSink | None, event: AgentProgressEvent) -> None:
    """Emit ``event`` if ``sink`` is not ``None``."""
    if sink is None:
        return
    await sink.emit(event)
