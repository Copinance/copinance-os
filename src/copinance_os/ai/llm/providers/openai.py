"""OpenAI Chat Completions LLM provider (text + function calling)."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator, Awaitable, Callable
from decimal import Decimal
from typing import Any

import structlog

_AsyncOpenAI: type[Any] | None = None
try:
    from openai import AsyncOpenAI as _ImportedAsyncOpenAI

    _AsyncOpenAI = _ImportedAsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Alias for optional dependency (tests patch this name; None when openai is not installed).
AsyncOpenAI: type[Any] | None = _AsyncOpenAI

from copinance_os.ai.llm.providers.base import LLMProvider
from copinance_os.ai.llm.streaming import LLMTextStreamEvent, TextStreamingMode
from copinance_os.ai.llm.tool_loop_streaming import (
    generate_turn_text_with_stream,
    maybe_emit_tool_round_rollback,
)
from copinance_os.core.execution_engine.question_driven_tool_summary import (
    build_partial_synthesis_message,
    is_tool_call_json_text,
)
from copinance_os.core.pipeline.tools.tool_executor import ToolExecutor
from copinance_os.core.progress.emit import maybe_emit_progress
from copinance_os.domain.models.agent_progress import IterationStartedEvent
from copinance_os.domain.models.llm_conversation import LLMConversationTurn
from copinance_os.domain.ports.progress import ProgressSink
from copinance_os.domain.ports.tools import Tool

logger = structlog.get_logger(__name__)


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


def _openai_tool_definitions(executor: ToolExecutor) -> list[dict[str, Any]]:
    """Build OpenAI ``tools`` payload from a :class:`ToolExecutor`."""
    out: list[dict[str, Any]] = []
    for name in executor.list_tools():
        tool = executor.get_tool(name)
        if not tool:
            continue
        schema = tool.get_schema()
        out.append(
            {
                "type": "function",
                "function": {
                    "name": schema.name,
                    "description": schema.description,
                    "parameters": schema.parameters,
                },
            }
        )
    return out


def _usage_from_openai(u: Any) -> dict[str, int]:
    if u is None:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    return {
        "input_tokens": int(getattr(u, "prompt_tokens", 0) or 0),
        "output_tokens": int(getattr(u, "completion_tokens", 0) or 0),
        "total_tokens": int(getattr(u, "total_tokens", 0) or 0),
    }


def _tool_calls_to_openai_dicts(raw: Any) -> list[dict[str, Any]]:
    """Normalize SDK tool call objects to serializable message dicts."""
    result: list[dict[str, Any]] = []
    for tc in raw or []:
        if hasattr(tc, "model_dump"):
            dumped = tc.model_dump()
            result.append(dumped)
            continue
        fn = getattr(tc, "function", None)
        result.append(
            {
                "id": getattr(tc, "id", "") or "",
                "type": getattr(tc, "type", "function") or "function",
                "function": {
                    "name": (fn.name if fn else "") or "",
                    "arguments": (fn.arguments if fn else None) or "{}",
                },
            }
        )
    return result


def _parse_function_calls_from_tool_calls(
    raw: list[dict[str, Any]], executor: ToolExecutor
) -> list[dict[str, Any]]:
    """Parse OpenAI ``tool_calls`` into ``{\"name\", \"args\"}`` for the tool loop."""
    calls: list[dict[str, Any]] = []
    for tc in raw:
        fn = tc.get("function") or {}
        name = fn.get("name")
        if not name or name not in executor.list_tools():
            continue
        raw_args = fn.get("arguments") or "{}"
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
        except json.JSONDecodeError:
            args = {}
        if not isinstance(args, dict):
            args = {}
        calls.append({"name": name, "args": args, "_tool_call_id": tc.get("id"), "_raw": tc})
    return calls


class OpenAIProvider(LLMProvider):
    """OpenAI API provider using the Chat Completions interface.

    Supports question-driven analysis via native function (tool) calling.

    Example:
        ```python
        from copinance_os.ai.llm.config import LLMConfig
        from copinance_os.ai.llm.providers.factory import LLMProviderFactory

        cfg = LLMConfig(provider="openai", api_key="...", model="gpt-4o-mini")
        provider = LLMProviderFactory.create_provider("openai", llm_config=cfg)
        ```
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gpt-4o-mini",
        base_url: str | None = None,
        temperature: float = 0.7,
        max_output_tokens: int | None = None,
        *,
        text_streaming_mode: TextStreamingMode = "auto",
        disable_native_text_stream: bool = False,
    ) -> None:
        self._api_key = api_key
        self._model_name = model_name
        self._base_url = base_url
        self._default_temperature = temperature
        self._default_max_output_tokens = max_output_tokens
        self._text_streaming_mode: TextStreamingMode = text_streaming_mode
        self._disable_native_text_stream = disable_native_text_stream
        self._client: Any = None

        if OPENAI_AVAILABLE and api_key and AsyncOpenAI is not None:
            try:
                client_kw: dict[str, Any] = {"api_key": api_key}
                if base_url:
                    client_kw["base_url"] = base_url
                self._client = AsyncOpenAI(**client_kw)
                logger.info("Initialized OpenAI provider", model=model_name)
            except Exception as e:
                logger.warning("Failed to initialize OpenAI client", error=str(e))
        else:
            logger.warning(
                "OpenAI not available",
                openai_available=OPENAI_AVAILABLE,
                api_key_provided=api_key is not None,
            )

    def _build_messages(
        self,
        system_prompt: str | None,
        prior_conversation: list[LLMConversationTurn] | None,
        user_prompt: str,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for t in prior_conversation or []:
            messages.append({"role": t.role, "content": t.content})
        messages.append({"role": "user", "content": user_prompt})
        return messages

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        if not OPENAI_AVAILABLE:
            raise RuntimeError("openai package is not installed")
        if not self._api_key or self._client is None:
            raise RuntimeError("OpenAI client is not initialized")

        messages = self._build_messages(system_prompt, None, prompt)
        temp = self._default_temperature if temperature is None else temperature
        max_tok = max_tokens if max_tokens is not None else self._default_max_output_tokens
        create_kw: dict[str, Any] = {
            "model": self._model_name,
            "messages": messages,
            "temperature": temp,
        }
        if max_tok is not None:
            create_kw["max_tokens"] = max_tok

        try:
            logger.debug(
                "Generating text with OpenAI",
                model=self._model_name,
                prompt_len=len(prompt),
            )
            resp = await self._client.chat.completions.create(**create_kw)
            msg = resp.choices[0].message
            return (msg.content or "").strip()
        except Exception as e:
            logger.error("OpenAI API call failed", error=str(e))
            raise

    async def is_available(self) -> bool:
        if not OPENAI_AVAILABLE or not self._api_key or self._client is None:
            return False
        try:
            await self.generate_text("ping", temperature=0.0, max_tokens=3)
            return True
        except Exception as e:
            logger.debug("OpenAI availability check failed", error=str(e))
            return False

    def get_provider_name(self) -> str:
        return "openai"

    def get_model_name(self) -> str | None:
        return self._model_name

    def supports_native_text_stream(self) -> bool:
        return not self._disable_native_text_stream

    async def _iter_native_text_stream(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float | None,
        max_tokens: int | None,
        **kwargs: Any,
    ) -> AsyncGenerator[LLMTextStreamEvent, None]:
        if not OPENAI_AVAILABLE or self._client is None:
            raise RuntimeError("OpenAI client is not initialized")
        messages = self._build_messages(system_prompt, None, prompt)
        temp = self._default_temperature if temperature is None else temperature
        max_tok = max_tokens if max_tokens is not None else self._default_max_output_tokens
        create_kw: dict[str, Any] = {
            "model": self._model_name,
            "messages": messages,
            "temperature": temp,
            "stream": True,
        }
        if max_tok is not None:
            create_kw["max_tokens"] = max_tok

        stream = await self._client.chat.completions.create(**create_kw)
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            piece = getattr(delta, "content", None) if delta else None
            if piece:
                yield LLMTextStreamEvent(
                    kind="text_delta",
                    text_delta=piece,
                    native_streaming=True,
                )
        yield LLMTextStreamEvent(kind="done", native_streaming=True)

    def _chat_create_kwargs(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
        max_tokens: int | None,
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        kw: dict[str, Any] = {
            "model": self._model_name,
            "messages": messages,
            "temperature": temperature,
            "tools": tools,
            "tool_choice": "auto",
        }
        if max_tokens is not None:
            kw["max_tokens"] = max_tokens
        return kw

    async def _chat_turn_non_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
        max_tokens: int | None,
        tools: list[dict[str, Any]],
    ) -> tuple[str, list[dict[str, Any]], dict[str, int]]:
        resp = await self._client.chat.completions.create(
            **self._chat_create_kwargs(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
            )
        )
        msg = resp.choices[0].message
        text = (msg.content or "").strip()
        raw_tc = msg.tool_calls
        dumped = _tool_calls_to_openai_dicts(raw_tc)
        return text, dumped, _usage_from_openai(getattr(resp, "usage", None))

    async def _chat_turn_stream(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float,
        max_tokens: int | None,
        tools: list[dict[str, Any]],
        on_stream_event: Callable[[LLMTextStreamEvent], Awaitable[None]],
    ) -> tuple[str, list[dict[str, Any]], dict[str, int]]:
        stream = await self._client.chat.completions.create(
            **self._chat_create_kwargs(
                messages, temperature=temperature, max_tokens=max_tokens, tools=tools
            ),
            stream=True,
        )
        content_parts: list[str] = []
        merged: dict[int, dict[str, Any]] = {}
        usage_out = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

        async for chunk in stream:
            u = getattr(chunk, "usage", None)
            if u is not None:
                usage_out = _usage_from_openai(u)
            if not chunk.choices:
                continue
            ch = chunk.choices[0]
            d = ch.delta
            if d is None:
                continue
            if getattr(d, "content", None):
                content_parts.append(d.content)
                await on_stream_event(
                    LLMTextStreamEvent(
                        kind="text_delta",
                        text_delta=d.content,
                        native_streaming=True,
                    )
                )
            tcalls = getattr(d, "tool_calls", None)
            if tcalls:
                for tc in tcalls:
                    idx = tc.index
                    if idx not in merged:
                        merged[idx] = {
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    if getattr(tc, "id", None):
                        merged[idx]["id"] = tc.id
                    fn = tc.function
                    if fn is not None:
                        if getattr(fn, "name", None):
                            merged[idx]["function"]["name"] = fn.name
                        if getattr(fn, "arguments", None):
                            merged[idx]["function"]["arguments"] += fn.arguments or ""

        ordered = [merged[i] for i in sorted(merged.keys())]
        return "".join(content_parts).strip(), ordered, usage_out

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
        if not OPENAI_AVAILABLE:
            raise RuntimeError("openai package is not installed")
        if not self._api_key or self._client is None:
            raise RuntimeError("OpenAI client is not initialized")

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

        executor = ToolExecutor(tools, progress_sink=progress_sink, run_id=run_id)
        oai_tools = _openai_tool_definitions(executor)
        messages = self._build_messages(system_prompt, prior_conversation, prompt)

        tool_calls_made: list[dict[str, Any]] = []
        usage_total: dict[str, int] = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        recent_tool_calls: list[tuple[str, tuple[tuple[str, Any], ...]]] = []
        max_recent_history = 3
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
                use_stream = bool(stream and on_stream_event is not None)
                logger.debug(
                    "OpenAI tool calling iteration",
                    iteration=iteration + 1,
                    max_iterations=max_iterations,
                    stream=use_stream,
                )
                if use_stream:
                    assert on_stream_event is not None  # use_stream iff stream and callback set
                    response_text, tool_call_dicts, u = await self._chat_turn_stream(
                        messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        tools=oai_tools,
                        on_stream_event=on_stream_event,
                    )
                else:
                    response_text, tool_call_dicts, u = await self._chat_turn_non_stream(
                        messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        tools=oai_tools,
                    )
                for k in usage_total:
                    usage_total[k] += u.get(k, 0)

                await maybe_emit_tool_round_rollback(
                    stream=stream,
                    on_stream_event=on_stream_event,
                    had_tool_calls=bool(tool_call_dicts),
                )

                if not tool_call_dicts:
                    break

                function_calls = _parse_function_calls_from_tool_calls(tool_call_dicts, executor)

                loop_detected = False
                for func_call in function_calls:
                    tool_name_check = func_call["name"]
                    tool_args_check = func_call.get("args", {})
                    sorted_items_check = tuple(sorted(tool_args_check.items()))
                    sig: tuple[str, tuple[tuple[str, Any], ...]] = (
                        tool_name_check,
                        sorted_items_check,
                    )
                    if sig in recent_tool_calls:
                        logger.warning(
                            "Detected tool call loop - same call repeated",
                            tool_name=tool_name_check,
                            args=tool_args_check,
                            iteration=iteration + 1,
                        )
                        loop_detected = True
                        break
                if loop_detected:
                    break

                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": response_text if response_text else None,
                    "tool_calls": tool_call_dicts,
                }
                messages.append(assistant_msg)

                tool_feedback_stop: str | None = None
                for call_idx, tc_dict in enumerate(tool_call_dicts):
                    parsed_one = _parse_function_calls_from_tool_calls([tc_dict], executor)
                    if not parsed_one:
                        fn = tc_dict.get("function") or {}
                        err_name = fn.get("name", "")
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tc_dict.get("id", ""),
                                "content": json.dumps(
                                    {
                                        "tool": err_name,
                                        "success": False,
                                        "error": "Tool not found or invalid JSON arguments",
                                    }
                                ),
                            }
                        )
                        continue

                    func_call = parsed_one[0]
                    tool_name = func_call["name"]
                    tool_args = func_call.get("args", {})
                    tc_id = func_call.get("_tool_call_id") or tc_dict.get("id", "")

                    logger.info("Executing tool", tool_name=tool_name, args=tool_args)
                    tool_result = await executor.execute_tool(
                        tool_name,
                        progress_iteration=iteration + 1,
                        progress_call_index=call_idx,
                        **tool_args,
                    )

                    sorted_items = tuple(sorted(tool_args.items()))
                    recent_tool_calls.append((tool_name, sorted_items))
                    if len(recent_tool_calls) > max_recent_history:
                        recent_tool_calls.pop(0)

                    response_data = None
                    if tool_result.success and tool_result.data is not None:
                        serialized_data = _make_json_serializable(tool_result.data)
                        if isinstance(serialized_data, list) and len(serialized_data) > 100:
                            response_data = {
                                "_truncated": True,
                                "_total_items": len(serialized_data),
                                "_items_shown": 100,
                                "data": serialized_data[:100],
                                "note": f"Response truncated: showing first 100 of {len(serialized_data)} items",
                            }
                        else:
                            response_data = serialized_data

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
                        result_data = {
                            "tool": tool_name,
                            "success": False,
                            "error": tool_result.error or "Unknown error",
                        }
                    else:
                        result_data = {"tool": tool_name, "success": True, "data": tool_result.data}
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

                    tool_result_json = json.dumps(_make_json_serializable(result_data), indent=2)
                    messages.append(
                        {"role": "tool", "tool_call_id": tc_id, "content": tool_result_json}
                    )

                    should_stop = (is_empty_result or has_invalid_params) and iteration >= 1
                    if should_stop:
                        allow_retry = tool_result.metadata and tool_result.metadata.get(
                            "allow_retry", False
                        )
                        if not allow_retry:
                            tool_feedback_stop = (
                                "IMPORTANT: Stop making tool calls now. "
                                "Provide a final answer from data received, or explain limitations."
                            )

                if tool_feedback_stop:
                    messages.append({"role": "user", "content": tool_feedback_stop})

            except Exception as e:
                iteration_error = e
                logger.error(
                    "Error in OpenAI tool calling iteration",
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
