"""GeminiProvider.generate_with_tools: native function calling (real
FunctionDeclaration/function_call parts, not the old three-regex JSON-in-text
scraping) plus the tool-calling loop batching same-turn calls through
ToolRuntime.run_batch instead of a strict one-at-a-time for-loop.

Fakes only the network boundary (_call_gemini_api) with response objects
shaped like real google-genai ``GenerateContentResponse`` objects
(``candidates[0].content.parts[i].function_call``/``.text``) — everything
downstream (_extract_response_text, _extract_function_calls_from_response,
the loop itself) runs for real, which is what actually proves native
extraction works end to end.
"""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from typing import Any, cast

import pytest

from copinance_os.ai.llm.providers.gemini import GeminiProvider
from copinance_os.core.pipeline.tools.tool_runtime import ToolRuntime
from copinance_os.domain.models.pipeline.tool_results import ToolResult
from copinance_os.domain.ports.tool_spec import ToolSpec
from copinance_os.domain.ports.tools import Tool, ToolSchema


def _function_call_part(name: str, args: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(text=None, function_call=SimpleNamespace(name=name, args=args))


def _text_part(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text, function_call=None)


def _fake_response(*, text: str | None, parts: list[SimpleNamespace]) -> SimpleNamespace:
    candidate = SimpleNamespace(content=SimpleNamespace(parts=parts))
    return SimpleNamespace(text=text, candidates=[candidate])


def _tool_call_turn(*calls: tuple[str, dict[str, Any]]) -> SimpleNamespace:
    """A turn where the model returns only native function_call parts (no text)."""
    return _fake_response(text=None, parts=[_function_call_part(n, a) for n, a in calls])


def _final_answer_turn(text: str) -> SimpleNamespace:
    return _fake_response(text=text, parts=[_text_part(text)])


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


def _provider() -> GeminiProvider:
    return GeminiProvider(api_key="fake-key", model_name="gemini-2.0-flash")


def _wire_fake_turns(provider: GeminiProvider, turns: list[SimpleNamespace]) -> None:
    turn_iter = iter(turns)

    async def _fake_call(*_args: Any, **_kwargs: Any) -> SimpleNamespace:
        return next(turn_iter)

    provider._call_gemini_api = _fake_call  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_native_function_call_parts_are_extracted_without_any_text_scraping() -> None:
    """The core Phase 2 claim: a response with ONLY function_call parts (no
    embedded JSON text at all) still yields the right tool calls — impossible
    for the old regex approach, which needed the tool call spelled out as
    JSON prose."""
    events: list[str] = []
    tools: list[Tool] = [_SlowEchoTool("get_a", 0.0, events)]
    provider = _provider()
    _wire_fake_turns(
        provider,
        [
            _tool_call_turn(("get_a", {"symbol": "AAPL"})),
            _final_answer_turn("Final answer."),
        ],
    )

    result = await provider.generate_with_tools(prompt="what about AAPL", tools=tools)

    assert result["text"] == "Final answer."
    assert [tc["tool"] for tc in result["tool_calls"]] == ["get_a"]


@pytest.mark.asyncio
async def test_nested_object_argument_round_trips_natively() -> None:
    """Exactly the case the old regexes could not express: a nested array
    argument (get_options_chain-style expiration_dates: [...]) surviving
    intact as a real typed value, not a string blob to re-parse."""
    events: list[str] = []
    tools: list[Tool] = [_SlowEchoTool("get_a", 0.0, events)]
    provider = _provider()
    nested_args = {"symbol": "AAPL", "expiration_dates": ["2026-01-16", "2026-02-20"]}
    _wire_fake_turns(
        provider,
        [
            _tool_call_turn(("get_a", nested_args)),
            _final_answer_turn("Final answer."),
        ],
    )

    result = await provider.generate_with_tools(prompt="options for AAPL", tools=tools)

    assert result["tool_calls"][0]["args"] == nested_args


@pytest.mark.asyncio
async def test_two_tool_calls_in_one_turn_run_concurrently() -> None:
    events: list[str] = []
    tools: list[Tool] = [_SlowEchoTool("get_a", 0.1, events), _SlowEchoTool("get_b", 0.1, events)]
    provider = _provider()
    _wire_fake_turns(
        provider,
        [
            _tool_call_turn(("get_a", {"symbol": "AAPL"}), ("get_b", {"symbol": "MSFT"})),
            _final_answer_turn("Final answer."),
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
async def test_tool_calls_preserve_original_order() -> None:
    events: list[str] = []
    tools: list[Tool] = [_SlowEchoTool("get_a", 0.0, events), _SlowEchoTool("get_b", 0.0, events)]
    provider = _provider()
    _wire_fake_turns(
        provider,
        [
            _tool_call_turn(("get_a", {"symbol": "AAPL"}), ("get_b", {"symbol": "MSFT"})),
            _final_answer_turn("Final answer."),
        ],
    )

    result = await provider.generate_with_tools(prompt="compare AAPL and MSFT", tools=tools)

    assert [tc["tool"] for tc in result["tool_calls"]] == ["get_a", "get_b"]


@pytest.mark.asyncio
async def test_response_with_no_function_call_parts_ends_the_loop() -> None:
    events: list[str] = []
    tools: list[Tool] = [_SlowEchoTool("get_a", 0.0, events)]
    provider = _provider()
    _wire_fake_turns(provider, [_final_answer_turn("No tools needed, here's the answer.")])

    result = await provider.generate_with_tools(prompt="what is 2+2", tools=tools)

    assert result["text"] == "No tools needed, here's the answer."
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
            _tool_call_turn(("get_a", {"symbol": "AAPL"})),
            _tool_call_turn(("get_a", {"symbol": "AAPL"})),
            _final_answer_turn("Final answer."),
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
            _tool_call_turn(("get_a", {"symbol": "AAPL"})),
            _tool_call_turn(("get_a", {"symbol": "AAPL"})),
            _tool_call_turn(("get_a", {"symbol": "AAPL"})),
            _final_answer_turn("Never reached."),
        ],
    )

    result = await provider.generate_with_tools(prompt="q", tools=tools)

    assert tool.call_count == 1
    assert result["text"] != "Never reached."
    assert result["synthesis_status"] == "partial"


@pytest.mark.asyncio
async def test_a_batch_of_three_distinct_parallel_calls_never_trips_loop_detection() -> None:
    """The false positive this whole fix targets: native function calling can
    issue several distinct calls in one turn — that must never look like a
    loop just because it filled the old fixed-size history window."""
    counting_tools = [_CountingTool("get_a"), _CountingTool("get_b"), _CountingTool("get_c")]
    tools: list[Tool] = cast(list[Tool], counting_tools)
    provider = _provider()
    _wire_fake_turns(
        provider,
        [
            _tool_call_turn(
                ("get_a", {"symbol": "AAPL"}),
                ("get_b", {"symbol": "MSFT"}),
                ("get_c", {"symbol": "GOOG"}),
            ),
            _final_answer_turn("Final answer."),
        ],
    )

    result = await provider.generate_with_tools(prompt="q", tools=tools)

    assert result["text"] == "Final answer."
    assert result["synthesis_status"] == "complete"
    assert all(t.call_count == 1 for t in counting_tools)


@pytest.mark.asyncio
async def test_validation_error_text_still_matches_the_tool_schema_hint_condition() -> None:
    """Regression: ToolRuntime validates every tool call via that tool's
    Pydantic args_model (see ToolSpec) before the legacy hand-rolled checker
    ever runs, so a missing/invalid param now produces a Pydantic "validation
    error for ..." message instead of the old "Missing required parameter: x"
    text. generate_with_tools' tool_schema-hint condition (gemini.py) keys off
    that error string — it must still match, or the hint silently stops
    firing for every tool."""
    events: list[str] = []
    tool = _SlowEchoTool("get_a", 0.0, events)
    runtime = ToolRuntime([ToolSpec.from_legacy(tool)])

    result = await runtime.execute_tool("get_a")  # missing required `symbol`

    assert result.success is False
    error_msg = result.error or ""
    assert (
        "must be one of" in error_msg
        or "Missing required parameter" in error_msg
        or "validation error" in error_msg
    )
