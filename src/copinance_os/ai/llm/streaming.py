"""Structured events for LLM text streaming (AI layer contract)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TextStreamingMode = Literal["auto", "native", "buffered"]


class LLMTextStreamEvent(BaseModel):
    """One unit emitted by `LLMProvider.generate_text_stream`.

    Consumers should concatenate `text_delta` events in order for the full answer.
    A successful stream ends with `kind="done"`. Failures use `kind="error"`.
    """

    model_config = {"extra": "forbid"}

    kind: Literal["text_delta", "done", "error", "rollback"]
    text_delta: str = ""
    error_message: str | None = None
    native_streaming: bool = Field(
        description="True if chunks came from provider-native streaming, False if buffered fallback."
    )
    usage: dict[str, int] | None = Field(
        default=None,
        description="Optional token usage on done, when the provider exposes it.",
    )


def normalize_text_streaming_mode(value: str | None) -> TextStreamingMode:
    """Return a valid mode; invalid values default to auto."""
    if value in ("auto", "native", "buffered"):
        return value  # type: ignore[return-value]
    return "auto"
