"""OllamaProvider.generate_with_tools: the tool-calling loop that now batches
same-turn tool calls through ToolRuntime.run_batch instead of a strict
one-at-a-time for-loop. Not previously covered by test_ollama.py, which never
drives generate_with_tools."""

from __future__ import annotations

import asyncio
import time
from typing import Any, cast

import pytest

from copinance_os.ai.llm.providers.ollama import OllamaProvider
from copinance_os.domain.models.pipeline.tool_results import ToolResult
from copinance_os.domain.ports.tools import Tool, ToolSchema


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


def _provider_with_fake_turns(texts: list[str]) -> OllamaProvider:
    provider = OllamaProvider()
    turns = iter(texts)

    async def _fake_turn(*_args: Any, **_kwargs: Any) -> str:
        return next(turns)

    provider._ollama_chat_turn = _fake_turn  # type: ignore[method-assign]
    return provider


@pytest.mark.asyncio
async def test_two_tool_calls_in_one_turn_run_concurrently() -> None:
    events: list[str] = []
    tools: list[Tool] = [_SlowEchoTool("get_a", 0.1, events), _SlowEchoTool("get_b", 0.1, events)]
    provider = _provider_with_fake_turns(
        [
            '{"tool": "get_a", "args": {"symbol": "AAPL"}}\n'
            '{"tool": "get_b", "args": {"symbol": "MSFT"}}',
            "Final answer.",
        ]
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
async def test_tool_calls_preserve_original_order() -> None:
    events: list[str] = []
    tools: list[Tool] = [_SlowEchoTool("get_a", 0.0, events), _SlowEchoTool("get_b", 0.0, events)]
    provider = _provider_with_fake_turns(
        [
            '{"tool": "get_a", "args": {"symbol": "AAPL"}}\n'
            '{"tool": "get_b", "args": {"symbol": "MSFT"}}',
            "Final answer.",
        ]
    )

    result = await provider.generate_with_tools(prompt="compare AAPL and MSFT", tools=tools)

    assert [tc["tool"] for tc in result["tool_calls"]] == ["get_a", "get_b"]


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
    provider = _provider_with_fake_turns(
        [
            '{"tool": "get_a", "args": {"symbol": "AAPL"}}',
            '{"tool": "get_a", "args": {"symbol": "AAPL"}}',
            "Final answer.",
        ]
    )

    result = await provider.generate_with_tools(prompt="q", tools=tools)

    assert tool.call_count == 1
    assert result["tool_calls"][0]["response"] == result["tool_calls"][1]["response"]


@pytest.mark.asyncio
async def test_third_identical_call_stops_the_loop_without_a_third_execution() -> None:
    tool = _CountingTool("get_a")
    tools: list[Tool] = [tool]
    provider = _provider_with_fake_turns(
        [
            '{"tool": "get_a", "args": {"symbol": "AAPL"}}',
            '{"tool": "get_a", "args": {"symbol": "AAPL"}}',
            '{"tool": "get_a", "args": {"symbol": "AAPL"}}',
            "Never reached.",
        ]
    )

    result = await provider.generate_with_tools(prompt="q", tools=tools)

    assert tool.call_count == 1
    assert result["text"] != "Never reached."
    assert result["synthesis_status"] == "partial"


@pytest.mark.asyncio
async def test_a_batch_of_three_distinct_parallel_calls_never_trips_loop_detection() -> None:
    """The false positive this whole fix targets: several distinct calls in
    one turn must never look like a loop just because it filled the old
    fixed-size history window."""
    counting_tools = [_CountingTool("get_a"), _CountingTool("get_b"), _CountingTool("get_c")]
    tools: list[Tool] = cast(list[Tool], counting_tools)
    provider = _provider_with_fake_turns(
        [
            '{"tool": "get_a", "args": {"symbol": "AAPL"}}\n'
            '{"tool": "get_b", "args": {"symbol": "MSFT"}}\n'
            '{"tool": "get_c", "args": {"symbol": "GOOG"}}',
            "Final answer.",
        ]
    )

    result = await provider.generate_with_tools(prompt="q", tools=tools)

    assert result["text"] == "Final answer."
    assert result["synthesis_status"] == "complete"
    assert all(t.call_count == 1 for t in counting_tools)
