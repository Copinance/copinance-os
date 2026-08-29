"""Anthropic (Claude) LLM provider — native tool use, prompt caching, strict schemas.

Phase 3 of the "faster, more reliable AI tool system" design doc. Differences
from OpenAI/Gemini worth calling out:

- **Every ``tool_result`` block for one turn goes in a single ``user`` message.**
  Anthropic's docs are explicit that splitting them across messages silently
  trains the model out of using parallel tool calls — this is the one thing
  that must never regress here.
- **Prompt caching**: one ``cache_control: {"type": "ephemeral"}`` breakpoint
  on the last block of ``system``. Anthropic's cache-eligible prefix order is
  tools -> system -> messages, so a single breakpoint at the end of ``system``
  covers both tools and system in one cache entry — no need for a second
  breakpoint on the tools list itself.
- **Strict tool schemas** (``ToolParam.strict = True``) — the model must
  produce arguments conforming exactly to the declared JSON Schema, the same
  guarantee ``strict`` gives on OpenAI.
- **Native error results**: a failed tool call becomes
  ``tool_result_block(is_error=True)``, not a ``success: false`` payload the
  model has to parse out of prose.

Not implemented in this pass:

- **Context editing** (``clear_tool_uses``-style beta context management) —
  the design doc calls for it to drop stale tool results from long
  conversations, but it's a beta feature gated behind specific request
  headers/fields this session could not verify against live API docs. Adding
  it with unverified syntax risks breaking every request; left for a
  follow-up once the current beta contract is confirmed.
- **Native token streaming** for the tool-calling loop. ``supports_native_text_stream``
  returns ``False``, so plain ``generate_text_stream`` already gets the base
  class's buffered fallback (one full-text delta, not token-by-token) for
  free; the tool loop below does the same — it calls the non-streaming
  Messages API and, when a caller asked for streaming, emits the whole
  response as one ``text_delta`` rather than real incremental tokens. This is
  a disclosed scope cut, not a bug: real incremental streaming needs the
  ``content_block_delta``/``input_json_delta`` event handling validated
  against a live account, which this environment doesn't have.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from decimal import Decimal
from typing import Any

import structlog
from typing_extensions import override

_anthropic: Any | None = None
try:
    import anthropic as _imported_anthropic

    _anthropic = _imported_anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# Alias for optional dependency (None when anthropic is not installed).
anthropic: Any | None = _anthropic

from copinance_os.ai.llm.providers.base import LLMProvider
from copinance_os.ai.llm.streaming import LLMTextStreamEvent, TextStreamingMode
from copinance_os.ai.llm.tool_loop_streaming import (
    generate_turn_text_with_stream,
    maybe_emit_tool_round_rollback,
)
from copinance_os.ai.llm.tool_repeat_tracking import REPEAT_NOTICE, ToolRepeatTracker
from copinance_os.ai.llm.tool_result_serialization import (
    budget_tool_result,
    compact_json_with_toon,
    per_call_max_chars,
)
from copinance_os.core.execution_engine.question_driven_tool_summary import (
    build_partial_synthesis_message,
    is_tool_call_json_text,
)
from copinance_os.core.pipeline.tools.tool_runtime import ToolCallRequest, ToolRuntime
from copinance_os.core.progress.emit import maybe_emit_progress
from copinance_os.domain.models.pipeline.agent_progress import IterationStartedEvent
from copinance_os.domain.models.pipeline.llm_conversation import LLMConversationTurn
from copinance_os.domain.models.pipeline.tool_results import ToolResult
from copinance_os.domain.ports.progress import ProgressSink
from copinance_os.domain.ports.tool_spec import ToolSpec
from copinance_os.domain.ports.tools import Tool

logger = structlog.get_logger(__name__)

DEFAULT_MAX_TOKENS = 4096


def _make_json_serializable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _make_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_json_serializable(item) for item in obj]
    if hasattr(obj, "model_dump"):
        return _make_json_serializable(obj.model_dump())
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    return str(obj)


def _strict_input_schema(parameters: dict[str, Any]) -> dict[str, Any]:
    """Copy ``parameters`` with ``additionalProperties: False`` set.

    Declaring ``strict: True`` without this is a lie to the API: strict tool
    use means the model's arguments conform *exactly* to the schema, which
    requires the schema to actually forbid extra properties. A copy, not a
    mutation — ``parameters`` is the same dict object ``ToolSpec.json_schema``
    (and every other provider) reads from; mutating it in place would leak
    this Anthropic-specific tightening into OpenAI/Gemini's schemas too.
    """
    return {**parameters, "additionalProperties": False}


def _anthropic_tool_definitions(runtime: ToolRuntime) -> list[dict[str, Any]]:
    """Build strict, cache-eligible Anthropic ``tools`` payload from a :class:`ToolRuntime`."""
    out: list[dict[str, Any]] = []
    for name in runtime.list_tools():
        tool = runtime.get_tool(name)
        if tool is None:
            continue
        schema = tool.get_schema()
        out.append(
            {
                "name": schema.name,
                "description": schema.description,
                "input_schema": _strict_input_schema(schema.parameters),
                "strict": True,
            }
        )
    return out


def _system_blocks(system_prompt: str | None) -> list[dict[str, Any]] | None:
    """One ``system`` text block with a cache breakpoint on it.

    Anthropic's cache-eligible prefix order is tools -> system -> messages, so
    a single ``cache_control`` here covers both tools and system in one cache
    entry (the design doc's "one cache_control breakpoint after tools +
    system") — no separate breakpoint needed on the tools list itself.
    """
    if not system_prompt:
        return None
    return [
        {
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"},
        }
    ]


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider — native tool use, prompt caching, strict schemas.

    Example:
        ```python
        from copinance_os.ai.llm.providers import AnthropicProvider

        provider = AnthropicProvider(api_key="your-api-key")
        response = await provider.generate_text("Analyze this instrument...")
        ```
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "claude-opus-5",
        temperature: float = 0.7,
        max_output_tokens: int | None = None,
        *,
        text_streaming_mode: TextStreamingMode = "auto",
        disable_native_text_stream: bool = False,
    ) -> None:
        self._api_key = api_key
        self._model_name = model_name
        self._default_temperature = temperature
        self._default_max_output_tokens = max_output_tokens
        self._text_streaming_mode: TextStreamingMode = text_streaming_mode
        self._disable_native_text_stream = disable_native_text_stream
        self._client: Any = None

        if ANTHROPIC_AVAILABLE and api_key and anthropic is not None:
            try:
                self._client = anthropic.AsyncAnthropic(api_key=api_key)
                logger.info("Initialized Anthropic provider", model=model_name)
            except Exception as e:
                logger.warning("Failed to initialize Anthropic client", error=str(e))
        else:
            logger.warning(
                "Anthropic not available",
                anthropic_available=ANTHROPIC_AVAILABLE,
                api_key_provided=api_key is not None,
            )

    def _max_tokens(self, max_tokens: int | None) -> int:
        return max_tokens or self._default_max_output_tokens or DEFAULT_MAX_TOKENS

    @override
    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        if not ANTHROPIC_AVAILABLE:
            raise RuntimeError("anthropic package is not installed")
        if not self._api_key or self._client is None:
            raise RuntimeError("Anthropic client is not initialized")

        create_kwargs: dict[str, Any] = {
            "model": self._model_name,
            "max_tokens": self._max_tokens(max_tokens),
            "messages": [{"role": "user", "content": prompt}],
        }
        system_blocks = _system_blocks(system_prompt)
        if system_blocks:
            create_kwargs["system"] = system_blocks
        # `temperature` is accepted here only for LLMProvider interface
        # compatibility — deliberately never sent. The models this provider
        # targets (Opus 5, Sonnet 5, Fable 5) reject a top-level `temperature`
        # with a 400; there is no sampling-temperature equivalent to forward
        # it as. A caller wanting a thoroughness/cost dial should pass
        # `output_config={"effort": "low"|"medium"|"high"|"xhigh"|"max"}`
        # via **kwargs instead — that flows through untouched below.
        create_kwargs.update(kwargs)

        response = await self._client.messages.create(**create_kwargs)
        return self._extract_text(response)

    @staticmethod
    def _extract_text(response: Any) -> str:
        if response is None:
            return ""
        parts = [
            block.text
            for block in getattr(response, "content", None) or []
            if getattr(block, "type", None) == "text"
        ]
        return "".join(parts)

    @staticmethod
    def _extract_tool_use_blocks(response: Any) -> list[Any]:
        return [
            block
            for block in getattr(response, "content", None) or []
            if getattr(block, "type", None) == "tool_use"
        ]

    @staticmethod
    def _usage_from_response(response: Any) -> dict[str, int]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        out = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }
        cache_read = getattr(usage, "cache_read_input_tokens", None)
        if cache_read:
            out["cache_read_input_tokens"] = int(cache_read)
        cache_creation = getattr(usage, "cache_creation_input_tokens", None)
        if cache_creation:
            out["cache_creation_input_tokens"] = int(cache_creation)
        return out

    @override
    async def is_available(self) -> bool:
        if not ANTHROPIC_AVAILABLE or not self._api_key or self._client is None:
            return False
        try:
            test_response = await self.generate_text("test", temperature=0.1, max_tokens=10)
            return bool(test_response)
        except Exception as e:
            logger.debug("Anthropic availability check failed", error=str(e))
            return False

    @override
    def get_provider_name(self) -> str:
        return "anthropic"

    @override
    def get_model_name(self) -> str | None:
        return self._model_name

    @override
    def supports_native_text_stream(self) -> bool:
        # See module docstring: real incremental streaming isn't implemented
        # yet. False routes generate_text_stream to the base class's buffered
        # fallback (one full-text delta) instead of raising.
        return False

    @override
    async def generate_with_tools(
        self,
        prompt: str,
        tools: list[Tool] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        max_iterations: int = 5,
        *,
        stream: bool = False,
        on_stream_event: Callable[[LLMTextStreamEvent], Awaitable[None]] | None = None,
        prior_conversation: list[LLMConversationTurn] | None = None,
        progress_sink: ProgressSink | None = None,
        run_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if not ANTHROPIC_AVAILABLE:
            raise RuntimeError("anthropic package is not installed")
        if not self._api_key or self._client is None:
            raise RuntimeError("Anthropic client is not initialized")

        if tools is None or len(tools) == 0:
            text = await generate_turn_text_with_stream(
                self,
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                on_stream_event=on_stream_event,
                **kwargs,
            )
            return {
                "text": text,
                "tool_calls": [],
                "iterations": 1,
                "synthesis_status": "complete",
                "llm_synthesis_error": None,
            }

        runtime = ToolRuntime(
            [ToolSpec.from_legacy(t) for t in tools], progress_sink=progress_sink, run_id=run_id
        )
        anthropic_tools = _anthropic_tool_definitions(runtime)
        system_blocks = _system_blocks(system_prompt)

        messages: list[dict[str, Any]] = []
        for t in prior_conversation or []:
            messages.append({"role": t.role, "content": t.content})
        messages.append({"role": "user", "content": prompt})

        tool_calls_made: list[dict[str, Any]] = []
        usage_total: dict[str, int] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        repeat_tracker: ToolRepeatTracker[ToolResult[Any]] = ToolRepeatTracker()
        iteration_error: Exception | None = None
        response_text = ""

        for iteration in range(max_iterations):
            try:
                if progress_sink is not None and run_id is not None:
                    await maybe_emit_progress(
                        progress_sink,
                        IterationStartedEvent(
                            run_id=run_id,
                            iteration=iteration + 1,
                            max_iterations=max_iterations,
                        ),
                    )
                logger.debug(
                    "Anthropic tool calling iteration",
                    iteration=iteration + 1,
                    max_iterations=max_iterations,
                )

                create_kwargs: dict[str, Any] = {
                    "model": self._model_name,
                    "max_tokens": self._max_tokens(max_tokens),
                    "messages": messages,
                    "tools": anthropic_tools,
                }
                if system_blocks:
                    create_kwargs["system"] = system_blocks
                # See generate_text: `temperature` is deliberately never sent
                # (Opus 5 / Sonnet 5 / Fable 5 reject it with a 400).

                response = await self._client.messages.create(**create_kwargs)
                response_text = self._extract_text(response)
                tool_use_blocks = self._extract_tool_use_blocks(response)

                u = self._usage_from_response(response)
                for k in usage_total:
                    usage_total[k] += u.get(k, 0)
                for extra_key in ("cache_read_input_tokens", "cache_creation_input_tokens"):
                    if extra_key in u:
                        usage_total[extra_key] = usage_total.get(extra_key, 0) + u[extra_key]

                if stream and on_stream_event and response_text:
                    # See module docstring: buffered, not token-incremental.
                    await on_stream_event(
                        LLMTextStreamEvent(
                            kind="text_delta", text_delta=response_text, native_streaming=False
                        )
                    )

                await maybe_emit_tool_round_rollback(
                    stream=stream,
                    on_stream_event=on_stream_event,
                    had_tool_calls=bool(tool_use_blocks),
                )

                if not tool_use_blocks:
                    break

                function_calls = [
                    {"name": block.name, "args": dict(block.input or {}), "_id": block.id}
                    for block in tool_use_blocks
                ]

                # Track occurrences up front — the count decides whether a call
                # executes, reuses a remembered result, or stops the loop
                # (design doc §6: the second identical call reuses the cached
                # prior result plus a nudge; only a third ends the round).
                occurrences = [
                    repeat_tracker.record(fc["name"], fc["args"]) for fc in function_calls
                ]
                if any(repeat_tracker.should_stop(fc["name"], fc["args"]) for fc in function_calls):
                    logger.warning(
                        "Stopping iteration due to detected loop",
                        iteration=iteration + 1,
                    )
                    break

                # Batch execution — parallel-safe calls run concurrently (see
                # ToolRuntime.run_batch) instead of one at a time. Only
                # first-occurrence calls execute; a repeat is served from the
                # tracker's remembered result instead of re-running the tool.
                # Every tool_use block still needs a matching tool_result
                # (Anthropic requires it even for a call we don't re-run).
                to_execute = [
                    (call_idx, func_call)
                    for call_idx, func_call in enumerate(function_calls)
                    if occurrences[call_idx] == 1
                ]
                executed = (
                    await runtime.run_batch(
                        [
                            ToolCallRequest(
                                name=func_call["name"],
                                args=func_call["args"],
                                call_index=call_idx,
                                iteration=iteration + 1,
                            )
                            for call_idx, func_call in to_execute
                        ]
                    )
                    if to_execute
                    else []
                )
                batch_results: list[ToolResult[Any]] = [None] * len(function_calls)  # type: ignore[list-item]
                for (call_idx, executed_call), executed_result in zip(
                    to_execute, executed, strict=True
                ):
                    repeat_tracker.remember(
                        executed_call["name"], executed_call["args"], executed_result
                    )
                    batch_results[call_idx] = executed_result
                for call_idx, func_call in enumerate(function_calls):
                    if occurrences[call_idx] == 1:
                        continue
                    cached_result = repeat_tracker.cached(func_call["name"], func_call["args"])
                    assert cached_result is not None, "occurrence 2 must have a remembered result"
                    batch_results[call_idx] = cached_result

                # Echo the model's own turn back verbatim (text + tool_use
                # blocks, with their exact ids) — Anthropic requires this for
                # the tool_result turn that follows to resolve correctly.
                assistant_content: list[dict[str, Any]] = []
                if response_text:
                    assistant_content.append({"type": "text", "text": response_text})
                assistant_content.extend(
                    {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
                    for block in tool_use_blocks
                )
                messages.append({"role": "assistant", "content": assistant_content})

                tool_result_blocks: list[dict[str, Any]] = []
                stop_suffix: str | None = None
                # A per-turn budget, not per-call: N parallel-safe calls in one
                # iteration must not return N x DEFAULT_MAX_RESULT_CHARS combined
                # (see per_call_max_chars) — the old serial loop made a per-call
                # constant self-limiting; parallel execution does not.
                per_call_budget = per_call_max_chars(len(function_calls))
                for call_idx, (func_call, tool_result) in enumerate(
                    zip(function_calls, batch_results, strict=True)
                ):
                    tool_name = func_call["name"]
                    tool_args = func_call["args"]

                    response_data = None
                    if tool_result.success and tool_result.data is not None:
                        response_data = budget_tool_result(
                            _make_json_serializable(tool_result.data),
                            tool_name=tool_name,
                            max_chars=per_call_budget,
                        )

                    tool_calls_made.append(
                        {
                            "tool": tool_name,
                            "args": tool_args,
                            "success": tool_result.success,
                            "error": tool_result.error,
                            "response": response_data,
                            "metadata": (
                                _make_json_serializable(tool_result.metadata)
                                if tool_result.metadata
                                else None
                            ),
                        }
                    )

                    is_empty_result = False
                    has_invalid_params = False
                    if tool_result.success:
                        invalid_symbols = [
                            "UNKNOWN",
                            "UNKNOWN_COMPANY",
                            "UNKNOWN_SYMBOL",
                            "N/A",
                            "NULL",
                        ]
                        if any(
                            str(v).upper() in invalid_symbols
                            for v in tool_args.values()
                            if isinstance(v, str)
                        ):
                            has_invalid_params = True
                        if (
                            tool_result.data is None
                            or tool_result.data == []
                            or tool_result.data == {}
                        ):
                            is_empty_result = True
                        elif isinstance(tool_result.data, dict):
                            has_data = any(
                                v not in ([], {}, None, "", 0) for v in tool_result.data.values()
                            )
                            if not has_data:
                                is_empty_result = True

                    if not tool_result.success:
                        result_data: dict[str, Any] = {
                            "tool": tool_name,
                            "success": False,
                            "error": tool_result.error or "Unknown error",
                        }
                    else:
                        result_data = {"tool": tool_name, "success": True, "data": response_data}
                        if is_empty_result or has_invalid_params:
                            warning_msg = ""
                            if has_invalid_params:
                                warning_msg += (
                                    "Tool was called with invalid parameters. "
                                    "Use the correct instrument symbol from the question. "
                                )
                            if is_empty_result:
                                warning_msg += (
                                    "Tool returned empty result. "
                                    "Invalid parameters or no data available. "
                                )
                                if tool_result.metadata and "suggestion" in tool_result.metadata:
                                    warning_msg += str(tool_result.metadata["suggestion"])
                            should_suggest_stop = True
                            if tool_result.metadata and tool_result.metadata.get(
                                "allow_retry", False
                            ):
                                should_suggest_stop = False
                            if should_suggest_stop:
                                warning_msg += (
                                    "Consider stopping and answering from available information."
                                )
                            result_data["warning"] = warning_msg

                    if occurrences[call_idx] == 2:
                        result_data["warning"] = (
                            f"{result_data.get('warning', '')} {REPEAT_NOTICE}".strip()
                        )

                    # Native error result: is_error=True, not a success:false
                    # payload the model has to parse out of prose.
                    tool_result_blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": func_call["_id"],
                            "content": compact_json_with_toon(_make_json_serializable(result_data)),
                            "is_error": not tool_result.success,
                        }
                    )

                    should_stop = (is_empty_result or has_invalid_params) and iteration >= 1
                    if should_stop:
                        allow_retry = tool_result.metadata and tool_result.metadata.get(
                            "allow_retry", False
                        )
                        if not allow_retry:
                            stop_suffix = (
                                "IMPORTANT: Stop making tool calls now. "
                                "Provide a final answer from data received, or explain limitations."
                            )

                # All tool_result blocks for this turn in ONE user message —
                # never split across messages (see module docstring). The stop
                # nudge, if any, is an extra text block in that same message
                # rather than a second consecutive user message (Anthropic
                # requires strict user/assistant alternation).
                user_content: list[dict[str, Any]] = list(tool_result_blocks)
                if stop_suffix:
                    user_content.append({"type": "text", "text": stop_suffix})
                messages.append({"role": "user", "content": user_content})

            except Exception as e:
                iteration_error = e
                logger.error(
                    "Error in Anthropic tool calling iteration",
                    error=str(e),
                    iteration=iteration + 1,
                )
                if iteration == 0:
                    text = await generate_turn_text_with_stream(
                        self,
                        prompt=prompt,
                        system_prompt=system_prompt,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        stream=stream,
                        on_stream_event=on_stream_event,
                        **kwargs,
                    )
                    return {
                        "text": text,
                        "tool_calls": [],
                        "iterations": 1,
                        "synthesis_status": "complete",
                        "llm_synthesis_error": None,
                    }
                break

        text_out = response_text
        synthesis_status = "complete"
        llm_synthesis_error: str | None = None
        partial_reason: str | None = None

        if tool_calls_made:
            if iteration_error is not None:
                synthesis_status = "partial"
                llm_synthesis_error = str(iteration_error)
                partial_reason = "LLM request failed after tools ran"
            elif is_tool_call_json_text(response_text):
                synthesis_status = "partial"
                partial_reason = (
                    "Tool-calling loop ended before a natural-language answer "
                    "(output still looked like a tool call, or the loop stopped early)."
                )
            elif not (response_text or "").strip():
                synthesis_status = "partial"
                partial_reason = (
                    "No final natural-language answer after tool calls (empty assistant text). "
                    "The loop may have stopped after repeated identical tool calls, or the last "
                    "model turn only requested tools."
                )

        if synthesis_status == "partial" and partial_reason:
            text_out = build_partial_synthesis_message(
                reason=partial_reason,
                error_detail=llm_synthesis_error,
                tool_calls=tool_calls_made,
            )
            logger.warning(
                "Question-driven synthesis incomplete; substituted deterministic tool summary",
                synthesis_status=synthesis_status,
                tool_calls_count=len(tool_calls_made),
            )

        result: dict[str, Any] = {
            "text": text_out,
            "tool_calls": tool_calls_made,
            "iterations": iteration + 1,
            "synthesis_status": synthesis_status,
            "llm_synthesis_error": llm_synthesis_error,
        }
        if any(usage_total.values()):
            result["llm_usage"] = dict(usage_total)
        return result
