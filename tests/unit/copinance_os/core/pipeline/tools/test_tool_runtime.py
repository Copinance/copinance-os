"""ToolRuntime: parallel execution, per-tool timeout, wall-clock deadline,
per-tool TTL cache, single-flight dedupe, and the metrics hook.

Mirrors the Phase 1 verification list from the "faster, more reliable AI tool
system" design doc: N parallel-safe tools complete in ~max not ~sum, a hanging
tool is killed at timeout_s and returns a structured result, and a ContextVar
is visible inside a gather-ed tool call.
"""

from __future__ import annotations

import asyncio
import contextvars
import time
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from copinance_os.core.pipeline.tools.tool_runtime import (
    ToolCallRequest,
    ToolRunMetric,
    ToolRuntime,
)
from copinance_os.data.cache import CacheManager
from copinance_os.data.cache.memory_cache import InMemoryCacheBackend
from copinance_os.domain.models.pipeline.tool_results import ToolResult
from copinance_os.domain.ports.tool_spec import ToolSpec


class _Args(BaseModel):
    model_config = ConfigDict(extra="allow")


def _spec(
    name: str,
    handler: Any,
    *,
    timeout_s: float = 20.0,
    parallel_safe: bool = True,
    cache_ttl_s: float | None = None,
    cacheable: bool = True,
    args_model: type[BaseModel] = _Args,
) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=name,
        args_model=args_model,
        handler=handler,
        timeout_s=timeout_s,
        parallel_safe=parallel_safe,
        cache_ttl_s=cache_ttl_s,
        cacheable=cacheable,
    )


async def _echo(**kwargs: Any) -> ToolResult[Any]:
    return ToolResult(success=True, data=kwargs)


@pytest.mark.asyncio
async def test_parallel_safe_calls_complete_in_roughly_max_not_sum() -> None:
    async def _slow(**kwargs: Any) -> ToolResult[Any]:
        await asyncio.sleep(0.2)
        return ToolResult(success=True, data=None)

    runtime = ToolRuntime([_spec("slow", _slow)] * 1)
    # Same spec name reused across calls is fine here — dedupe would collapse
    # identical args, so give each call distinct args to force 4 real runs.
    calls = [ToolCallRequest(name="slow", args={"i": i}) for i in range(4)]

    t0 = time.monotonic()
    results = await runtime.run_batch(calls)
    elapsed = time.monotonic() - t0

    assert all(r.success for r in results)
    # ~0.2s if parallel; ~0.8s if serialized. Generous margin for CI jitter.
    assert elapsed < 0.5


@pytest.mark.asyncio
async def test_non_parallel_safe_calls_run_sequentially_not_concurrently() -> None:
    concurrent_count = 0
    max_concurrent = 0

    async def _tracked(**kwargs: Any) -> ToolResult[Any]:
        nonlocal concurrent_count, max_concurrent
        concurrent_count += 1
        max_concurrent = max(max_concurrent, concurrent_count)
        await asyncio.sleep(0.05)
        concurrent_count -= 1
        return ToolResult(success=True, data=None)

    runtime = ToolRuntime([_spec("seq", _tracked, parallel_safe=False)])
    calls = [ToolCallRequest(name="seq", args={"i": i}) for i in range(3)]

    results = await runtime.run_batch(calls)

    assert all(r.success for r in results)
    assert max_concurrent == 1


@pytest.mark.asyncio
async def test_hanging_tool_is_killed_at_timeout_and_returns_structured_result() -> None:
    async def _hangs(**kwargs: Any) -> ToolResult[Any]:
        await asyncio.sleep(10)
        return ToolResult(success=True, data=None)

    runtime = ToolRuntime([_spec("hangs", _hangs, timeout_s=0.05)])
    result = await runtime.execute_tool("hangs")

    assert result.success is False
    assert "timed out" in (result.error or "")
    assert result.metadata.get("status") == "timeout"


@pytest.mark.asyncio
async def test_call_past_deadline_is_skipped_not_run() -> None:
    ran = False

    async def _marks_ran(**kwargs: Any) -> ToolResult[Any]:
        nonlocal ran
        ran = True
        return ToolResult(success=True, data=None)

    runtime = ToolRuntime([_spec("marks", _marks_ran)])
    past_deadline = time.monotonic() - 1.0

    results = await runtime.run_batch(
        [ToolCallRequest(name="marks", args={})], deadline=past_deadline
    )

    assert ran is False
    assert results[0].success is False
    assert results[0].metadata.get("reason") == "budget"


@pytest.mark.asyncio
async def test_unknown_tool_returns_error_result_not_an_exception() -> None:
    runtime = ToolRuntime([_spec("known", _echo)])
    result = await runtime.execute_tool("nope", symbol="AAPL")
    assert result.success is False
    assert "not found" in (result.error or "")


@pytest.mark.asyncio
async def test_results_preserve_request_order_regardless_of_scheduling() -> None:
    async def _by_delay(**kwargs: Any) -> ToolResult[Any]:
        await asyncio.sleep(0.05 if kwargs.get("slow") else 0.0)
        return ToolResult(success=True, data=kwargs["tag"])

    runtime = ToolRuntime([_spec("t", _by_delay)])
    calls = [
        ToolCallRequest(name="t", args={"tag": "a", "slow": True}),
        ToolCallRequest(name="t", args={"tag": "b", "slow": False}),
        ToolCallRequest(name="t", args={"tag": "c", "slow": True}),
    ]

    results = await runtime.run_batch(calls)
    assert [r.data for r in results] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_single_flight_dedupe_runs_identical_call_only_once() -> None:
    call_count = 0
    seen_symbols: list[str] = []

    async def _counted(**kwargs: Any) -> ToolResult[Any]:
        nonlocal call_count
        call_count += 1
        seen_symbols.append(kwargs["symbol"])
        await asyncio.sleep(0.01)
        return ToolResult(success=True, data=kwargs["symbol"])

    runtime = ToolRuntime([_spec("counted", _counted)])
    calls = [
        ToolCallRequest(name="counted", args={"symbol": "AAPL"}),
        ToolCallRequest(name="counted", args={"symbol": "AAPL"}),  # identical -> dedupe
        ToolCallRequest(name="counted", args={"symbol": "MSFT"}),  # different -> separate run
    ]

    results = await runtime.run_batch(calls)

    assert call_count == 2  # not 3 -> the duplicate AAPL call never re-ran the handler
    assert sorted(seen_symbols) == ["AAPL", "MSFT"]
    assert results[0].data == results[1].data == "AAPL"  # both dedupe to the same run
    assert results[2].data == "MSFT"


@pytest.mark.asyncio
async def test_single_flight_dedupe_still_emits_progress_for_every_call_index() -> None:
    """Regression: a call that dedupes onto another call's in-flight
    execution must still get its own started/finished progress events — the
    model asked for both calls, even though only one actually runs. Before
    the fix, only the first occurrence in a batch emitted anything, so the
    progress stream silently dropped every duplicate position."""

    class _RecordingSink:
        def __init__(self) -> None:
            self.events: list[Any] = []

        async def emit(self, event: Any) -> None:
            self.events.append(event)

    async def _counted(**kwargs: Any) -> ToolResult[Any]:
        await asyncio.sleep(0.01)
        return ToolResult(success=True, data=kwargs["symbol"])

    sink = _RecordingSink()
    runtime = ToolRuntime([_spec("counted", _counted)], progress_sink=sink, run_id="run-1")
    calls = [
        ToolCallRequest(name="counted", args={"symbol": "AAPL"}, call_index=0),
        ToolCallRequest(name="counted", args={"symbol": "AAPL"}, call_index=1),  # dedupes
    ]

    await runtime.run_batch(calls)

    started = [e for e in sink.events if type(e).__name__ == "ToolStartedEvent"]
    finished = [e for e in sink.events if type(e).__name__ == "ToolFinishedEvent"]
    assert len(started) == 2
    assert len(finished) == 2
    assert {e.call_index for e in started} == {0, 1}


@pytest.mark.asyncio
async def test_semaphore_wait_is_charged_against_the_deadline() -> None:
    """Regression: `remaining` was computed before acquiring the semaphore,
    so a long wait for a concurrency slot went uncounted against the
    deadline — a call could queue past the deadline for a slot and still be
    given the tool's full timeout_s once it got one. The deadline check must
    happen after the semaphore is acquired so queueing time counts."""
    release_first = asyncio.Event()
    second_ran = False

    async def _holds_the_slot(**kwargs: Any) -> ToolResult[Any]:
        await release_first.wait()
        return ToolResult(success=True, data=None)

    async def _marks_ran(**kwargs: Any) -> ToolResult[Any]:
        nonlocal second_ran
        second_ran = True
        return ToolResult(success=True, data=None)

    runtime = ToolRuntime(
        [_spec("holder", _holds_the_slot), _spec("second", _marks_ran)],
        max_concurrency=1,
    )
    # Deadline is already in the past by the time the second call could ever
    # acquire the semaphore (it's queued behind the first, which never
    # releases until we tell it to) — it must be skipped, not run with a
    # fresh full timeout once the slot frees up.
    deadline = time.monotonic() + 0.05

    async def _release_after_deadline_passes() -> None:
        await asyncio.sleep(0.15)
        release_first.set()

    release_task = asyncio.ensure_future(_release_after_deadline_passes())
    try:
        results = await runtime.run_batch(
            [
                ToolCallRequest(name="holder", args={}),
                ToolCallRequest(name="second", args={}),
            ],
            deadline=deadline,
        )
    finally:
        await release_task

    assert second_ran is False
    assert results[1].success is False
    assert results[1].metadata.get("reason") == "budget"


@pytest.mark.asyncio
async def test_run_batch_handles_list_valued_args_without_crashing() -> None:
    """A list-valued arg (e.g. get_options_chain's expiration_dates: [...])
    is unhashable — run_batch's single-flight dedupe must not use it as a raw
    dict key. Regression test for a real bug caught via the Gemini native
    function-calling integration tests."""

    async def _echo(**kwargs: Any) -> ToolResult[Any]:
        return ToolResult(success=True, data=kwargs)

    runtime = ToolRuntime([_spec("chain", _echo)])
    calls = [
        ToolCallRequest(
            name="chain", args={"symbol": "AAPL", "expiration_dates": ["2026-01-16", "2026-02-20"]}
        ),
        ToolCallRequest(
            name="chain", args={"symbol": "AAPL", "expiration_dates": ["2026-01-16", "2026-02-20"]}
        ),
        ToolCallRequest(name="chain", args={"symbol": "AAPL", "expiration_dates": ["2026-03-20"]}),
    ]

    results = await runtime.run_batch(calls)

    assert results[0].data == results[1].data  # identical list args -> deduped
    third_data = results[2].data
    assert isinstance(third_data, dict)
    assert third_data["expiration_dates"] == ["2026-03-20"]


@pytest.mark.asyncio
async def test_contextvar_is_visible_inside_a_gathered_tool_call() -> None:
    """asyncio.gather copies the current Context into each child task — the
    exact mechanism apps/backend's current_chat_user_id ContextVar relies on."""
    current_user_id: contextvars.ContextVar[str] = contextvars.ContextVar("current_user_id")
    token = current_user_id.set("user-123")
    seen: list[str] = []

    async def _reads_contextvar(**kwargs: Any) -> ToolResult[Any]:
        seen.append(current_user_id.get())
        return ToolResult(success=True, data=None)

    try:
        runtime = ToolRuntime([_spec("reads", _reads_contextvar)])
        calls = [ToolCallRequest(name="reads", args={"i": i}) for i in range(3)]
        await runtime.run_batch(calls)
    finally:
        current_user_id.reset(token)

    assert seen == ["user-123"] * 3


@pytest.mark.asyncio
async def test_per_tool_ttl_cache_hits_on_second_identical_call_across_batches() -> None:
    call_count = 0

    async def _counted(**kwargs: Any) -> ToolResult[Any]:
        nonlocal call_count
        call_count += 1
        return ToolResult(success=True, data={"n": call_count})

    cache_manager = CacheManager(backend=InMemoryCacheBackend())
    runtime = ToolRuntime(
        [_spec("cached", _counted, cache_ttl_s=60.0)], cache_manager=cache_manager
    )

    first = await runtime.execute_tool("cached", symbol="AAPL")
    second = await runtime.execute_tool("cached", symbol="AAPL")

    assert call_count == 1  # second call served from cache, handler not re-run
    assert first.data == second.data


@pytest.mark.asyncio
async def test_tool_without_cache_ttl_is_never_cached() -> None:
    call_count = 0

    async def _counted(**kwargs: Any) -> ToolResult[Any]:
        nonlocal call_count
        call_count += 1
        return ToolResult(success=True, data=None)

    cache_manager = CacheManager(backend=InMemoryCacheBackend())
    runtime = ToolRuntime([_spec("uncached", _counted)], cache_manager=cache_manager)

    await runtime.execute_tool("uncached", symbol="AAPL")
    await runtime.execute_tool("uncached", symbol="AAPL")

    assert call_count == 2


@pytest.mark.asyncio
async def test_cacheable_false_is_never_cached_even_with_a_ttl_set() -> None:
    """Safety mechanism: a tool whose result depends on ambient identity
    (e.g. a ContextVar-read "current user") must never be cached keyed only
    on its arguments, or one user's result leaks to another. cacheable=False
    is the escape hatch, checked before cache_ttl_s."""
    call_count = 0

    async def _counted(**kwargs: Any) -> ToolResult[Any]:
        nonlocal call_count
        call_count += 1
        return ToolResult(success=True, data={"n": call_count})

    cache_manager = CacheManager(backend=InMemoryCacheBackend())
    runtime = ToolRuntime(
        [_spec("user_scoped", _counted, cache_ttl_s=60.0, cacheable=False)],
        cache_manager=cache_manager,
    )

    first = await runtime.execute_tool("user_scoped", symbol="AAPL")
    second = await runtime.execute_tool("user_scoped", symbol="AAPL")

    assert call_count == 2
    assert first.data != second.data


@pytest.mark.asyncio
async def test_cache_key_uses_validated_args_not_raw_call_args() -> None:
    """{"symbol": "AAPL"} and {"symbol": "AAPL", "interval": "1d"} (interval's
    own schema default) must hash identically — the cache key is built from
    validated args, after schema defaults are filled in, not the raw call."""

    class _IntervalArgs(BaseModel):
        model_config = ConfigDict(extra="allow")
        symbol: str
        interval: str = "1d"

    call_count = 0

    async def _counted(**kwargs: Any) -> ToolResult[Any]:
        nonlocal call_count
        call_count += 1
        return ToolResult(success=True, data={"n": call_count})

    cache_manager = CacheManager(backend=InMemoryCacheBackend())
    runtime = ToolRuntime(
        [_spec("historical", _counted, cache_ttl_s=60.0, args_model=_IntervalArgs)],
        cache_manager=cache_manager,
    )

    first = await runtime.execute_tool("historical", symbol="AAPL")
    second = await runtime.execute_tool("historical", symbol="AAPL", interval="1d")

    assert call_count == 1  # same effective call -> cache hit, not a miss
    assert first.data == second.data


@pytest.mark.asyncio
async def test_cache_hit_carries_provenance_metadata() -> None:
    """A cached result must be distinguishable from a fresh one — the legacy
    _execute_with_cache path added cached/cached_at/cache_warning; a prompt
    that insists on no bare, unsourced numbers depends on this surviving."""

    async def _counted(**kwargs: Any) -> ToolResult[Any]:
        return ToolResult(success=True, data={"price": 100})

    cache_manager = CacheManager(backend=InMemoryCacheBackend())
    runtime = ToolRuntime(
        [_spec("cached", _counted, cache_ttl_s=60.0)], cache_manager=cache_manager
    )

    first = await runtime.execute_tool("cached", symbol="AAPL")
    second = await runtime.execute_tool("cached", symbol="AAPL")

    assert "cached" not in first.metadata
    assert second.metadata["cached"] is True
    assert "cached_at" in second.metadata
    assert "cache_warning" in second.metadata


@pytest.mark.asyncio
async def test_progress_sink_exception_on_started_does_not_break_execution() -> None:
    """A bare asyncio.gather in run_batch neither cancels nor awaits sibling
    tasks when one raises — so a ProgressSink.emit() that raises here must
    never propagate out of _execute_one, or it leaks the other tasks in the
    same batch."""

    class _RaisingSink:
        async def emit(self, event: Any) -> None:
            raise RuntimeError("sink exploded")

    runtime = ToolRuntime([_spec("echo", _echo)], progress_sink=_RaisingSink(), run_id="run-1")

    result = await runtime.execute_tool("echo", symbol="AAPL")

    assert result.success is True


@pytest.mark.asyncio
async def test_metrics_hook_fires_with_duration_and_outcome() -> None:
    events: list[ToolRunMetric] = []

    runtime = ToolRuntime([_spec("echo", _echo)], metrics_hook=events.append)
    await runtime.execute_tool("echo", symbol="AAPL")

    assert len(events) == 1
    assert events[0].tool_name == "echo"
    assert events[0].success is True
    assert events[0].duration_s >= 0.0


@pytest.mark.asyncio
async def test_metrics_hook_reports_cache_hit() -> None:
    events: list[ToolRunMetric] = []
    cache_manager = CacheManager(backend=InMemoryCacheBackend())
    runtime = ToolRuntime(
        [_spec("cached", _echo, cache_ttl_s=60.0)],
        cache_manager=cache_manager,
        metrics_hook=events.append,
    )

    await runtime.execute_tool("cached", symbol="AAPL")
    await runtime.execute_tool("cached", symbol="AAPL")

    assert events[0].cache_hit is False
    assert events[1].cache_hit is True


@pytest.mark.asyncio
async def test_metrics_hook_exceptions_do_not_break_execution() -> None:
    def _raises(_event: ToolRunMetric) -> None:
        raise RuntimeError("metrics backend down")

    runtime = ToolRuntime([_spec("echo", _echo)], metrics_hook=_raises)
    result = await runtime.execute_tool("echo", symbol="AAPL")
    assert result.success is True
