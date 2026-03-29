"""Helpers for streaming text inside multi-turn tool loops."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from copinance_os.ai.llm.providers.base import LLMProvider
from copinance_os.ai.llm.streaming import LLMTextStreamEvent


async def generate_turn_text_with_stream(
    provider: LLMProvider,
    *,
    prompt: str,
    system_prompt: str | None,
    temperature: float | None,
    max_tokens: int | None,
    stream: bool,
    on_stream_event: Callable[[LLMTextStreamEvent], Awaitable[None]] | None,
    **kwargs: Any,
) -> str:
    """Single LLM turn: non-streaming, or streaming with optional live deltas."""
    if not stream or on_stream_event is None:
        return await provider.generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    parts: list[str] = []
    async for ev in provider.generate_text_stream(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=temperature if temperature is not None else 0.7,
        max_tokens=max_tokens,
        stream_mode="auto",
        **kwargs,
    ):
        if ev.kind == "text_delta":
            parts.append(ev.text_delta)
            await on_stream_event(ev)
        elif ev.kind == "error":
            raise RuntimeError(ev.error_message or "LLM stream error")
        elif ev.kind == "done":
            break
    return "".join(parts)


async def maybe_emit_tool_round_rollback(
    *,
    stream: bool,
    on_stream_event: Callable[[LLMTextStreamEvent], Awaitable[None]] | None,
    had_tool_calls: bool,
) -> None:
    """If we streamed tokens but the turn contained tool calls, notify consumer to discard display."""
    if stream and on_stream_event and had_tool_calls:
        await on_stream_event(
            LLMTextStreamEvent(kind="rollback", text_delta="", native_streaming=False)
        )
