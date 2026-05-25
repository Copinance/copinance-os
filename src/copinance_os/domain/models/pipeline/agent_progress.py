"""Structured progress events for agentic analysis (integrator / SSE contract).

Events are JSON-serialisable Pydantic models with a discriminating ``kind`` field.
``schema_version`` is bumped when the shape of any event type changes incompatibly.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

AGENT_PROGRESS_SCHEMA_VERSION = 1


class RunStartedEvent(BaseModel):
    """Analysis run accepted; question-driven agent work is starting."""

    model_config = {"extra": "forbid"}

    schema_version: int = Field(default=AGENT_PROGRESS_SCHEMA_VERSION, ge=1)
    kind: Literal["run_started"] = "run_started"
    run_id: str
    execution_type: str
    phase: Literal["question_driven"] = "question_driven"
    symbol: str | None = None
    market_index: str | None = None


class RunCompletedEvent(BaseModel):
    """Run finished successfully (business logic completed; see ``RunJobResult`` for payload)."""

    model_config = {"extra": "forbid"}

    schema_version: int = Field(default=AGENT_PROGRESS_SCHEMA_VERSION, ge=1)
    kind: Literal["run_completed"] = "run_completed"
    run_id: str
    success: bool


class RunFailedEvent(BaseModel):
    """Run failed or was rejected before completion."""

    model_config = {"extra": "forbid"}

    schema_version: int = Field(default=AGENT_PROGRESS_SCHEMA_VERSION, ge=1)
    kind: Literal["run_failed"] = "run_failed"
    run_id: str
    error_message: str


class IterationStartedEvent(BaseModel):
    """One LLM+tools iteration in the agent loop (1-based ``iteration``)."""

    model_config = {"extra": "forbid"}

    schema_version: int = Field(default=AGENT_PROGRESS_SCHEMA_VERSION, ge=1)
    kind: Literal["iteration_started"] = "iteration_started"
    run_id: str
    iteration: int = Field(ge=1)
    max_iterations: int = Field(ge=1)


class LlmStreamProgressEvent(BaseModel):
    """LLM streaming token lifecycle (aligns with ``LLMTextStreamEvent``)."""

    model_config = {"extra": "forbid"}

    schema_version: int = Field(default=AGENT_PROGRESS_SCHEMA_VERSION, ge=1)
    kind: Literal["llm_stream"] = "llm_stream"
    run_id: str
    stream_kind: Literal["text_delta", "done", "error", "rollback"]
    text_delta: str = ""
    error_message: str | None = None
    native_streaming: bool = False


class ToolStartedEvent(BaseModel):
    """A tool invocation is about to execute (arguments are summarised, not full payloads)."""

    model_config = {"extra": "forbid"}

    schema_version: int = Field(default=AGENT_PROGRESS_SCHEMA_VERSION, ge=1)
    kind: Literal["tool_started"] = "tool_started"
    run_id: str
    tool_name: str
    args_summary: str = ""
    iteration: int | None = Field(default=None, ge=1)
    call_index: int | None = Field(default=None, ge=0)


class ToolFinishedEvent(BaseModel):
    """Tool invocation finished; ``result_summary`` is truncated for UI, not a full tool body."""

    model_config = {"extra": "forbid"}

    schema_version: int = Field(default=AGENT_PROGRESS_SCHEMA_VERSION, ge=1)
    kind: Literal["tool_finished"] = "tool_finished"
    run_id: str
    tool_name: str
    success: bool
    duration_ms: float = Field(ge=0.0)
    result_summary: str | None = None


class GatheringContextEvent(BaseModel):
    """Deterministic phases before or between LLM turns (prompts, tool bundle, aggregation)."""

    model_config = {"extra": "forbid"}

    schema_version: int = Field(default=AGENT_PROGRESS_SCHEMA_VERSION, ge=1)
    kind: Literal["gathering_context"] = "gathering_context"
    run_id: str
    phase: Literal["building_prompts", "loading_tools", "aggregating"] = "building_prompts"
    detail: str | None = None


class SynthesisPhaseEvent(BaseModel):
    """Final narrative synthesis milestone (provider-dependent)."""

    model_config = {"extra": "forbid"}

    schema_version: int = Field(default=AGENT_PROGRESS_SCHEMA_VERSION, ge=1)
    kind: Literal["synthesis_phase"] = "synthesis_phase"
    run_id: str
    phase: Literal["started", "completed"] = "started"


AgentProgressRoot = Annotated[
    RunStartedEvent
    | RunCompletedEvent
    | RunFailedEvent
    | IterationStartedEvent
    | LlmStreamProgressEvent
    | ToolStartedEvent
    | ToolFinishedEvent
    | GatheringContextEvent
    | SynthesisPhaseEvent,
    Field(discriminator="kind"),
]

AgentProgressEvent = (
    RunStartedEvent
    | RunCompletedEvent
    | RunFailedEvent
    | IterationStartedEvent
    | LlmStreamProgressEvent
    | ToolStartedEvent
    | ToolFinishedEvent
    | GatheringContextEvent
    | SynthesisPhaseEvent
)

_agent_progress_adapter: TypeAdapter[AgentProgressRoot] = TypeAdapter(AgentProgressRoot)


def parse_agent_progress_event(data: object) -> AgentProgressEvent:
    """Validate a JSON-like object as an :class:`AgentProgressRoot` union member."""
    return _agent_progress_adapter.validate_python(data)
