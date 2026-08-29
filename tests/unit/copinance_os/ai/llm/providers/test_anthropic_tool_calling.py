"""AnthropicProvider.generate_with_tools: native tool use, strict schemas, and
the one hard requirement from the design doc — every tool_result block for a
turn must land in a single user message, never split across messages (that
silently trains the model out of parallel tool calls).

Fakes only the network boundary (client.messages.create) with response
objects shaped like real Anthropic ``Message`` objects
(``content: [TextBlock | ToolUseBlock]``, ``usage``) — everything downstream
runs for real.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from typing import Any, cast

import pytest

from copinance_os.ai.llm.providers.anthropic import (
    AnthropicProvider,
    _anthropic_tool_definitions,
    _strict_input_schema,
)
from copinance_os.core.pipeline.tools.tool_runtime import ToolRuntime
from copinance_os.domain.models.pipeline.tool_results import ToolResult
from copinance_os.domain.ports.tool_spec import ToolSpec
from copinance_os.domain.ports.tools import Tool, ToolSchema


def _tool_use_block(id_: str, name: str, args: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=args)


def _text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _usage(
    input_tokens: int = 10,
    output_tokens: int = 5,
    cache_read: int | None = None,
    cache_creation: int | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_input_tokens=cache_read,
        cache_creation_input_tokens=cache_creation,
    )


def _response(*blocks: SimpleNamespace, usage: SimpleNamespace | None = None) -> SimpleNamespace:
    return SimpleNamespace(content=list(blocks), usage=usage or _usage())


class _SlowEchoTool(Tool):
    def __init__(self, name: str, delay_s: float, events: list[str]) -> None:
        self._name = name
        self._delay_s = delay_s
        self._events = events

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self._name,
            description=f"Echo tool {self._name}",
            parameters={
                "type": "object",
                "properties": {"symbol": {"type": "string", "description": "symbol"}},
                "required": ["symbol"],
            },
        )

    def get_name(self) -> str:
        return self._name

    def get_description(self) -> str:
        return f"Echo tool {self._name}"

    async def execute(self, **kwargs: Any) -> ToolResult[Any]:
        self._events.append(f"{self._name}:start")
        await asyncio.sleep(self._delay_s)
        self._events.append(f"{self._name}:end")
        return ToolResult(success=True, data={"symbol": kwargs.get("symbol"), "tool": self._name})


class _FailingTool(_SlowEchoTool):
    async def execute(self, **kwargs: Any) -> ToolResult[Any]:
        return ToolResult(success=False, data=None, error="symbol not found")


def _provider() -> AnthropicProvider:
    return AnthropicProvider(api_key="fake-key", model_name="claude-opus-5")


def _wire_fake_turns(provider: AnthropicProvider, turns: list[SimpleNamespace]) -> None:
    turn_iter = iter(turns)

    async def _fake_create(**kwargs: Any) -> SimpleNamespace:
        return next(turn_iter)

    provider._client = SimpleNamespace(messages=SimpleNamespace(create=_fake_create))


@pytest.mark.asyncio
async def test_tools_are_declared_strict_with_cache_control_on_system() -> None:
    events: list[str] = []
    tools: list[Tool] = [_SlowEchoTool("get_a", 0.0, events)]
    provider = _provider()
    captured: dict[str, Any] = {}

    async def _fake_create(**kwargs: Any) -> SimpleNamespace:
        captured.update(kwargs)
        return _response(_text_block("Final answer."))

    provider._client = SimpleNamespace(messages=SimpleNamespace(create=_fake_create))

    await provider.generate_with_tools(
        prompt="what about AAPL", tools=tools, system_prompt="be helpful"
    )

    assert captured["tools"][0]["name"] == "get_a"
    assert captured["tools"][0]["strict"] is True
    # strict:True is a lie without this — it means "arguments conform exactly
    # to the schema", which requires the schema to actually forbid extras.
    assert captured["tools"][0]["input_schema"]["additionalProperties"] is False
    assert captured["system"][0]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_strict_schema_tightening_does_not_mutate_the_shared_schema_dict() -> None:
    """_strict_input_schema must copy, not mutate — tool.get_schema().parameters
    is the same dict object other providers (and repeated calls) read from."""
    events: list[str] = []
    tool = _SlowEchoTool("get_a", 0.0, events)
    original_schema = tool.get_schema().parameters
    assert "additionalProperties" not in original_schema

    tightened = _strict_input_schema(original_schema)

    assert tightened["additionalProperties"] is False
    assert "additionalProperties" not in original_schema  # untouched
    assert "additionalProperties" not in tool.get_schema().parameters


@pytest.mark.asyncio
async def test_two_tool_calls_in_one_turn_run_concurrently() -> None:
    events: list[str] = []
    tools: list[Tool] = [_SlowEchoTool("get_a", 0.1, events), _SlowEchoTool("get_b", 0.1, events)]
    provider = _provider()
    _wire_fake_turns(
        provider,
        [
            _response(
                _tool_use_block("call_a", "get_a", {"symbol": "AAPL"}),
                _tool_use_block("call_b", "get_b", {"symbol": "MSFT"}),
            ),
            _response(_text_block("Final answer.")),
        ],
    )

    t0 = time.monotonic()
    result = await provider.generate_with_tools(prompt="compare AAPL and MSFT", tools=tools)
    elapsed = time.monotonic() - t0

    assert result["text"] == "Final answer."
    assert len(result["tool_calls"]) == 2
    assert events.index("get_a:start") < events.index("get_b:end")
    assert events.index("get_b:start") < events.index("get_a:end")
    assert elapsed < 0.18


@pytest.mark.asyncio
async def test_nested_object_argument_round_trips() -> None:
    events: list[str] = []
    tools: list[Tool] = [_SlowEchoTool("get_a", 0.0, events)]
    provider = _provider()
    nested_args = {"symbol": "AAPL", "expiration_dates": ["2026-01-16", "2026-02-20"]}
    _wire_fake_turns(
        provider,
        [
            _response(_tool_use_block("call_a", "get_a", nested_args)),
            _response(_text_block("Final answer.")),
        ],
    )

    result = await provider.generate_with_tools(prompt="options for AAPL", tools=tools)

    assert result["tool_calls"][0]["args"] == nested_args


@pytest.mark.asyncio
async def test_all_tool_results_for_one_turn_land_in_a_single_user_message() -> None:
    """The one thing that must never regress: Anthropic's docs say splitting
    tool_result blocks across messages silently trains the model out of
    parallel tool use."""
    events: list[str] = []
    tools: list[Tool] = [_SlowEchoTool("get_a", 0.0, events), _SlowEchoTool("get_b", 0.0, events)]
    provider = _provider()
    captured_calls: list[dict[str, Any]] = []

    turns = iter(
        [
            _response(
                _tool_use_block("call_a", "get_a", {"symbol": "AAPL"}),
                _tool_use_block("call_b", "get_b", {"symbol": "MSFT"}),
            ),
            _response(_text_block("Final answer.")),
        ]
    )

    async def _fake_create(**kwargs: Any) -> SimpleNamespace:
        captured_calls.append(kwargs)
        return next(turns)

    provider._client = SimpleNamespace(messages=SimpleNamespace(create=_fake_create))

    await provider.generate_with_tools(prompt="compare AAPL and MSFT", tools=tools)

    # Second API call's messages: the tail should be exactly one user message
    # holding both tool_result blocks, not two separate user messages.
    second_call_messages = captured_calls[1]["messages"]
    user_messages_after_assistant = [m for m in second_call_messages if m["role"] == "user"][1:]
    assert len(user_messages_after_assistant) == 1
    tool_result_content = user_messages_after_assistant[0]["content"]
    tool_use_ids = [
        block["tool_use_id"] for block in tool_result_content if block["type"] == "tool_result"
    ]
    assert tool_use_ids == ["call_a", "call_b"]


@pytest.mark.asyncio
async def test_failed_tool_call_produces_is_error_true_not_a_text_payload() -> None:
    events: list[str] = []
    tools: list[Tool] = [_FailingTool("get_a", 0.0, events)]
    provider = _provider()
    captured_calls: list[dict[str, Any]] = []

    turns = iter(
        [
            _response(_tool_use_block("call_a", "get_a", {"symbol": "BOGUS"})),
            _response(_text_block("Could not find that symbol.")),
        ]
    )

    async def _fake_create(**kwargs: Any) -> SimpleNamespace:
        captured_calls.append(kwargs)
        return next(turns)

    provider._client = SimpleNamespace(messages=SimpleNamespace(create=_fake_create))

    result = await provider.generate_with_tools(prompt="what about BOGUS", tools=tools)

    assert result["tool_calls"][0]["success"] is False
    tool_result_block = captured_calls[1]["messages"][-1]["content"][0]
    assert tool_result_block["is_error"] is True


@pytest.mark.asyncio
async def test_usage_includes_cache_tokens_when_present() -> None:
    events: list[str] = []
    tools: list[Tool] = [_SlowEchoTool("get_a", 0.0, events)]
    provider = _provider()
    _wire_fake_turns(
        provider,
        [
            _response(
                _text_block("Final answer."),
                usage=_usage(input_tokens=100, output_tokens=20, cache_read=80),
            )
        ],
    )

    result = await provider.generate_with_tools(prompt="hi", tools=tools)

    assert result["llm_usage"]["cache_read_input_tokens"] == 80


@pytest.mark.asyncio
async def test_response_with_no_tool_use_blocks_ends_the_loop() -> None:
    events: list[str] = []
    tools: list[Tool] = [_SlowEchoTool("get_a", 0.0, events)]
    provider = _provider()
    _wire_fake_turns(provider, [_response(_text_block("No tools needed."))])

    result = await provider.generate_with_tools(prompt="what is 2+2", tools=tools)

    assert result["text"] == "No tools needed."
    assert result["tool_calls"] == []
    assert events == []


class _CountingTool(Tool):
    """Counts real executions — used to prove a repeated call is served from
    the tracker's remembered result rather than re-run."""

    def __init__(self, name: str) -> None:
        self._name = name
        self.call_count = 0

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self._name,
            description=f"Counting tool {self._name}",
            parameters={
                "type": "object",
                "properties": {"symbol": {"type": "string", "description": "symbol"}},
                "required": ["symbol"],
            },
        )

    def get_name(self) -> str:
        return self._name

    def get_description(self) -> str:
        return f"Counting tool {self._name}"

    async def execute(self, **kwargs: Any) -> ToolResult[Any]:
        self.call_count += 1
        return ToolResult(success=True, data={"symbol": kwargs.get("symbol"), "n": self.call_count})


@pytest.mark.asyncio
async def test_second_identical_call_reuses_cached_result_and_continues() -> None:
    tool = _CountingTool("get_a")
    tools: list[Tool] = [tool]
    provider = _provider()
    _wire_fake_turns(
        provider,
        [
            _response(_tool_use_block("call_1", "get_a", {"symbol": "AAPL"})),
            _response(_tool_use_block("call_2", "get_a", {"symbol": "AAPL"})),
            _response(_text_block("Final answer.")),
        ],
    )

    result = await provider.generate_with_tools(prompt="q", tools=tools)

    assert tool.call_count == 1
    assert result["tool_calls"][0]["response"] == result["tool_calls"][1]["response"]


@pytest.mark.asyncio
async def test_third_identical_call_stops_the_loop_without_a_third_execution() -> None:
    tool = _CountingTool("get_a")
    tools: list[Tool] = [tool]
    provider = _provider()
    _wire_fake_turns(
        provider,
        [
            _response(_tool_use_block("call_1", "get_a", {"symbol": "AAPL"})),
            _response(_tool_use_block("call_2", "get_a", {"symbol": "AAPL"})),
            _response(_tool_use_block("call_3", "get_a", {"symbol": "AAPL"})),
            _response(_text_block("Never reached.")),
        ],
    )

    result = await provider.generate_with_tools(prompt="q", tools=tools)

    assert tool.call_count == 1
    assert result["text"] != "Never reached."
    assert result["synthesis_status"] == "partial"


@pytest.mark.asyncio
async def test_a_batch_of_three_distinct_parallel_calls_never_trips_loop_detection() -> None:
    """The false positive this whole fix targets: native tool use can issue
    several distinct calls in one turn — that must never look like a loop
    just because it filled the old fixed-size history window."""
    counting_tools = [_CountingTool("get_a"), _CountingTool("get_b"), _CountingTool("get_c")]
    tools: list[Tool] = cast(list[Tool], counting_tools)
    provider = _provider()
    _wire_fake_turns(
        provider,
        [
            _response(
                _tool_use_block("call_a", "get_a", {"symbol": "AAPL"}),
                _tool_use_block("call_b", "get_b", {"symbol": "MSFT"}),
                _tool_use_block("call_c", "get_c", {"symbol": "GOOG"}),
            ),
            _response(_text_block("Final answer.")),
        ],
    )

    result = await provider.generate_with_tools(prompt="q", tools=tools)

    assert result["text"] == "Final answer."
    assert result["synthesis_status"] == "complete"
    assert all(t.call_count == 1 for t in counting_tools)


@pytest.mark.asyncio
async def test_from_legacy_and_to_legacy_tool_round_trip_through_anthropic_definitions() -> None:
    """Sanity check that the same ToolSpec.from_legacy path used by every
    other provider works for the tool-definition builder here too."""
    events: list[str] = []
    tool = _SlowEchoTool("get_a", 0.0, events)
    runtime = ToolRuntime([ToolSpec.from_legacy(tool)])

    defs = _anthropic_tool_definitions(runtime)
    assert defs[0]["name"] == "get_a"
    assert defs[0]["input_schema"]["required"] == ["symbol"]
