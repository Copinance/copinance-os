"""Default stdout/stderr handler for LLM streaming (execution layer; no Rich dependency)."""

from __future__ import annotations

import sys

from copinance_os.ai.llm.streaming import LLMTextStreamEvent


async def stdout_llm_stream_handler(ev: LLMTextStreamEvent) -> None:
    """Print stream events to the terminal; rollback prints a short notice on stderr."""
    if ev.kind == "text_delta":
        print(ev.text_delta, end="", flush=True)
    elif ev.kind == "rollback":
        print(file=sys.stderr)
        print("…tool round (continuing after tool calls)", file=sys.stderr, flush=True)
