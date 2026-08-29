"""OpenAIProvider.generate_with_tools: the tool-calling loop that now batches
same-turn tool calls through ToolRuntime.run_batch instead of a strict
one-at-a-time for-loop. generate_with_tools had no direct unit test before this
refactor (only a fully-mocked-provider test in test_agentic.py, which never
exercises this loop's internals), so this file also closes that gap.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Iterator
from typing import Any, cast

import pytest

from copinance_os.ai.llm.providers.openai import OpenAIProvider
from copinance_os.domain.models.pipeline.tool_results import ToolResult
from copinance_os.domain.ports.tools import Tool, ToolSchema


def _tool_call_dict(call_id: str, name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


class _SlowEchoTool(Tool):
    """Records call order/timing; used to prove same-turn calls run concurrently."""

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


def _provider() -> OpenAIProvider:
    return OpenAIProvider(api_key="fake-key", model_name="gpt-4o-mini")


@pytest.mark.asyncio
async def test_two_tool_calls_in_one_turn_run_concurrently() -> None:
    events: list[str] = []
    tools: list[Tool] = [_SlowEchoTool("get_a", 0.1, events), _SlowEchoTool("get_b", 0.1, events)]
    provider = _provider()

    turns: Iterator[tuple[str, list[dict[str, Any]], dict[str, Any]]] = iter(
        [
            (
                "",
                [
                    _tool_call_dict("call_a", "get_a", {"symbol": "AAPL"}),
                    _tool_call_dict("call_b", "get_b", {"symbol": "MSFT"}),
                ],
                {},
            ),
            ("Final answer.", [], {}),
        ]
    )

    async def _fake_turn(*_args: Any, **_kwargs: Any) -> tuple[str, list[dict[str, Any]], dict]:
        return next(turns)

    provider._chat_turn_non_stream = _fake_turn  # type: ignore[method-assign]

    t0 = time.monotonic()
    result = await provider.generate_with_tools(prompt="compare AAPL and MSFT", tools=tools)
    elapsed = time.monotonic() - t0

    assert result["text"] == "Final answer."
    assert len(result["tool_calls"]) == 2
    # Both tools' start events precede either end event -> they overlapped.
    assert events.index("get_a:start") < events.index("get_b:end")
    assert events.index("get_b:start") < events.index("get_a:end")
    # ~0.1s if concurrent, ~0.2s if serialized.
    assert elapsed < 0.18


@pytest.mark.asyncio
async def test_tool_result_messages_preserve_original_call_order() -> None:
    events: list[str] = []
    tools: list[Tool] = [_SlowEchoTool("get_a", 0.0, events), _SlowEchoTool("get_b", 0.0, events)]
    provider = _provider()

    captured_messages: list[list[dict[str, Any]]] = []
    turns: Iterator[tuple[str, list[dict[str, Any]], dict[str, Any]]] = iter(
        [
            (
                "",
                [
                    _tool_call_dict("call_a", "get_a", {"symbol": "AAPL"}),
                    _tool_call_dict("call_b", "get_b", {"symbol": "MSFT"}),
                ],
                {},
            ),
            ("Final answer.", [], {}),
        ]
    )

    async def _fake_turn(messages: list[dict[str, Any]], **_kwargs: Any):
        captured_messages.append([dict(m) for m in messages])
        return next(turns)

    provider._chat_turn_non_stream = _fake_turn  # type: ignore[method-assign]

    await provider.generate_with_tools(prompt="compare AAPL and MSFT", tools=tools)

    # Second call's messages include both tool results, in original tool_call order.
    second_call_messages = captured_messages[1]
    tool_msgs = [m for m in second_call_messages if m.get("role") == "tool"]
    assert [m["tool_call_id"] for m in tool_msgs] == ["call_a", "call_b"]


@pytest.mark.asyncio
async def test_unparseable_call_gets_error_message_without_breaking_the_others() -> None:
    events: list[str] = []
    tools: list[Tool] = [_SlowEchoTool("get_a", 0.0, events)]
    provider = _provider()

    turns: Iterator[tuple[str, list[dict[str, Any]], dict[str, Any]]] = iter(
        [
            (
                "",
                [
                    _tool_call_dict("call_unknown", "does_not_exist", {"symbol": "AAPL"}),
                    _tool_call_dict("call_a", "get_a", {"symbol": "AAPL"}),
                ],
                {},
            ),
            ("Final answer.", [], {}),
        ]
    )

    async def _fake_turn(*_args: Any, **_kwargs: Any):
        return next(turns)

    provider._chat_turn_non_stream = _fake_turn  # type: ignore[method-assign]

    result = await provider.generate_with_tools(prompt="q", tools=tools)

    assert result["text"] == "Final answer."
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["tool"] == "get_a"


class _CountingTool(Tool):
    """Counts real executions — used to prove a repeated call is served from
    the tracker's cache, not re-run."""

    def __init__(self, name: str) -> None:
        self._name = name
        self.call_count = 0

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self._name,
            description=self._name,
            parameters={
                "type": "object",
                "properties": {"symbol": {"type": "string", "description": "symbol"}},
                "required": ["symbol"],
            },
        )

    def get_name(self) -> str:
        return self._name

    def get_description(self) -> str:
        return self._name

    async def execute(self, **kwargs: Any) -> ToolResult[Any]:
        self.call_count += 1
        return ToolResult(success=True, data={"n": self.call_count})


@pytest.mark.asyncio
async def test_second_identical_call_reuses_cached_result_and_continues() -> None:
    tool = _CountingTool("get_a")
    provider = _provider()

    turns: Iterator[tuple[str, list[dict[str, Any]], dict[str, Any]]] = iter(
        [
            ("", [_tool_call_dict("call_1", "get_a", {"symbol": "AAPL"})], {}),
            ("", [_tool_call_dict("call_2", "get_a", {"symbol": "AAPL"})], {}),
            ("Final answer.", [], {}),
        ]
    )
    captured_messages: list[list[dict[str, Any]]] = []

    async def _fake_turn(messages: list[dict[str, Any]], **_kwargs: Any):
        captured_messages.append([dict(m) for m in messages])
        return next(turns)

    provider._chat_turn_non_stream = _fake_turn  # type: ignore[method-assign]

    result = await provider.generate_with_tools(prompt="q", tools=[tool])

    assert tool.call_count == 1  # second identical call never re-executed
    assert result["text"] == "Final answer."
    assert len(result["tool_calls"]) == 2  # both requests still get a reply
    assert result["tool_calls"][0]["response"] == result["tool_calls"][1]["response"]

    # The 2nd call's tool message must carry the repeat notice as a nudge.
    third_call_messages = captured_messages[2]
    tool_msg = next(m for m in third_call_messages if m.get("tool_call_id") == "call_2")
    assert "already made earlier" in tool_msg["content"]


@pytest.mark.asyncio
async def test_third_identical_call_stops_the_loop_without_a_third_execution() -> None:
    """The exact bug parallelism amplified: 'any repeat, immediately' broke
    the whole run on a single legitimate repeat. Now it takes three."""
    tool = _CountingTool("get_a")
    provider = _provider()

    turns: Iterator[tuple[str, list[dict[str, Any]], dict[str, Any]]] = iter(
        [
            ("", [_tool_call_dict("call_1", "get_a", {"symbol": "AAPL"})], {}),
            ("", [_tool_call_dict("call_2", "get_a", {"symbol": "AAPL"})], {}),
            ("", [_tool_call_dict("call_3", "get_a", {"symbol": "AAPL"})], {}),
            ("Should never be reached.", [], {}),
        ]
    )

    async def _fake_turn(*_args: Any, **_kwargs: Any):
        return next(turns)

    provider._chat_turn_non_stream = _fake_turn  # type: ignore[method-assign]

    result = await provider.generate_with_tools(prompt="q", tools=[tool])

    assert tool.call_count == 1  # only ever executed once, not three times
    assert result["text"] != "Should never be reached."
    assert result["synthesis_status"] == "partial"


@pytest.mark.asyncio
async def test_a_batch_of_three_distinct_parallel_calls_never_trips_loop_detection() -> None:
    """The false positive this whole fix targets: native function calling can
    issue several distinct calls in one turn — that must never look like a
    loop just because it filled the old fixed-size history window."""
    counting_tools = [_CountingTool("get_a"), _CountingTool("get_b"), _CountingTool("get_c")]
    tools: list[Tool] = cast(list[Tool], counting_tools)
    provider = _provider()

    turns: Iterator[tuple[str, list[dict[str, Any]], dict[str, Any]]] = iter(
        [
            (
                "",
                [
                    _tool_call_dict("call_a", "get_a", {"symbol": "AAPL"}),
                    _tool_call_dict("call_b", "get_b", {"symbol": "MSFT"}),
                    _tool_call_dict("call_c", "get_c", {"symbol": "GOOG"}),
                ],
                {},
            ),
            ("Final answer.", [], {}),
        ]
    )

    async def _fake_turn(*_args: Any, **_kwargs: Any):
        return next(turns)

    provider._chat_turn_non_stream = _fake_turn  # type: ignore[method-assign]

    result = await provider.generate_with_tools(prompt="q", tools=tools)

    assert result["text"] == "Final answer."
    assert result["synthesis_status"] == "complete"
    assert all(t.call_count == 1 for t in counting_tools)
