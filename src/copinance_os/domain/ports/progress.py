"""Port for emitting structured agent/analysis progress (UI, SSE, logging bridges)."""

from __future__ import annotations

from typing import Protocol

from copinance_os.domain.models.pipeline.agent_progress import AgentProgressEvent


class ProgressSink(Protocol):
    """Async consumer of :class:`~copinance_os.domain.models.pipeline.agent_progress.AgentProgressEvent`.

    Implementations typically forward to an SSE/WebSocket writer or an in-memory queue.
    Must not block the event loop on I/O; use ``asyncio``-friendly sinks.
    """

    async def emit(self, event: AgentProgressEvent) -> None:
        """Emit one progress event."""
        ...
