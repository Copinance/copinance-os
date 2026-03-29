"""Multi-turn LLM conversation turns for question-driven (analyzer) workflows."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError


class LLMConversationTurn(BaseModel):
    """One message in an analyzer conversation (user or assistant)."""

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1)


def validate_conversation_history_pairs(turns: list[LLMConversationTurn]) -> None:
    """Ensure history is alternating user → assistant … and ends with an assistant."""
    if not turns:
        return
    if len(turns) % 2 != 0:
        raise ValueError(
            "conversation_history must contain complete user–assistant pairs (even length); "
            "the latest user message must be passed separately as `question`."
        )
    for i, t in enumerate(turns):
        expected: Literal["user", "assistant"] = "user" if i % 2 == 0 else "assistant"
        if t.role != expected:
            raise ValueError(
                f"conversation_history at index {i}: expected role '{expected}', got '{t.role}'."
            )


def parse_conversation_history(raw: Any) -> list[LLMConversationTurn]:
    """Parse ``conversation_history`` from job context (list of dicts); validates user/assistant pairs."""
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("conversation_history must be a list of {role, content} objects.")
    try:
        turns = [LLMConversationTurn.model_validate(item) for item in raw]
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    validate_conversation_history_pairs(turns)
    return turns
