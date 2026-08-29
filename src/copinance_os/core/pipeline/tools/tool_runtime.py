"""``ToolRuntime`` — the ``ToolSpec``-aware successor to ``ToolExecutor``.

Adds, on top of what ``ToolExecutor`` already does (lookup, progress events,
error-to-result conversion):

- **Parallel execution.** ``run_batch`` gathers every ``parallel_safe`` call in
  the batch concurrently under a bounded semaphore; calls marked
  ``parallel_safe=False`` run afterwards, one at a time. (This is a
  deliberate simplification, not full mutual exclusion against the parallel
  group — see ``run_batch``'s docstring.) ``asyncio.gather`` copies the
  current ``contextvars.Context`` into each child task, so request-scoped
  ContextVars (``current_chat_user_id`` etc. in apps/backend's
  ``app/ai/tools/base.py``) are visible inside a gathered tool call with no
  extra plumbing.
- **Per-tool timeout.** ``asyncio.wait_for(..., spec.timeout_s)`` — today
  nothing bounds an individual tool; a hung call ate the whole iteration
  budget.
- **Wall-clock deadline.** ``run_batch(..., deadline=...)`` takes a
  ``time.monotonic()`` timestamp; a call that can't be started before it
  returns a structured ``skipped`` result instead of never running or blowing
  the outer budget.
- **Per-tool TTL cache**, using ``CacheManager``'s existing per-entry
  ``ttl=`` (``CacheManager.set(tool_name, data, ttl=timedelta(...), **kwargs)``
  already overrides the manager-wide ``default_ttl`` at read time — see
  ``cache_manager.py``). ``ToolSpec.cache_ttl_s`` is the one place this now
  needs to be set, instead of one manager-wide TTL silently applying to every
  tool. The cache key is built from **validated** args (post
  ``args_model.model_validate``), not the raw call — so a schema default
  filled in by validation (e.g. ``interval="1d"``) doesn't make two
  semantically-identical calls hash differently and miss each other. A
  cache hit carries the same provenance the legacy ``_execute_with_cache``
  path did (``cached``/``cached_at``/``cache_warning`` in ``metadata``) —
  load-bearing for a prompt that insists on no bare, unsourced numbers.
  ``ToolSpec.cacheable`` (default ``True``) is the escape hatch for a tool
  whose result depends on ambient identity rather than its arguments (a
  ContextVar-read "current user", say) — set it ``False`` at ``from_legacy``
  time for any such tool *before* wiring a ``cache_manager`` into a runtime
  that will execute it, or its cache key (which has no user dimension) will
  serve one user's result to another.
- **Single-flight dedupe** for identical ``(name, args)`` calls within one
  batch — a repeated call awaits the first call's task instead of re-running.
- **Metrics** via an optional ``metrics_hook`` callback (one ``ToolRunMetric``
  per completed call) — kept decoupled from any specific metrics backend
  (Prometheus isn't a copinance-os dependency; apps/backend wires this to
  ``COPINANCE_TOOL_CALLS`` and friends).

None of ``deadline=``, ``cache_manager=``, or ``metrics_hook=`` are passed by
any provider loop yet — parallel execution and per-tool timeouts (both
argument-free) are the only pieces live today. Wiring the cache in particular
needs one more thing settled first: a ``from_legacy``-wrapped tool that was
constructed with its own ``cache_manager`` (i.e. already does its own caching
via the legacy ``_execute_with_cache`` path) would double up with this cache
rather than replace it — the two layers would silently coexist on the same
underlying ``CacheManager`` and the same key scheme, which happens to be
harmless today (see ``_cache_get``/``_cache_set``'s key derivation matching
the legacy one) but is wasteful and confusing. Wire ``cache_manager=`` only
once that overlap is resolved (e.g. constructing ``from_legacy``-wrapped
tools with ``use_cache=False`` when they're headed into a ``ToolRuntime``
that has its own cache).
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from pydantic import BaseModel

from copinance_os.core.progress.emit import maybe_emit_progress
from copinance_os.core.progress.redaction import summarize_for_tool_args, summarize_tool_result
from copinance_os.data.cache import CacheManager
from copinance_os.domain.models.pipeline.agent_progress import ToolFinishedEvent, ToolStartedEvent
from copinance_os.domain.models.pipeline.tool_results import ToolResult
from copinance_os.domain.ports.progress import ProgressSink
from copinance_os.domain.ports.tool_spec import ToolSpec
from copinance_os.domain.ports.tools import Tool

logger = structlog.get_logger(__name__)

DEFAULT_MAX_CONCURRENCY = 8


class ToolRunMetric(BaseModel):
    """One completed (or skipped) tool call, for an optional metrics_hook."""

    tool_name: str
    duration_s: float
    success: bool
    cache_hit: bool = False
    skipped_reason: str | None = None


@dataclass(frozen=True)
class ToolCallRequest:
    """One tool invocation within a ``run_batch`` round."""

    name: str
    args: dict[str, Any] = field(default_factory=dict)
    call_index: int = 0
    iteration: int | None = None


def _skipped_result(reason: str) -> ToolResult[Any]:
    return ToolResult(
        success=False,
        data=None,
        error=f"skipped: {reason}",
        metadata={"status": "skipped", "reason": reason},
    )


def _dedupe_key(name: str, args: dict[str, Any]) -> tuple[str, str]:
    # A list- or dict-valued arg (e.g. get_options_chain's expiration_dates:
    # [...]) is unhashable, so the key can't be a raw tuple of (k, v) pairs —
    # it's used as a dict key below, which requires hashability. A sorted JSON
    # dump is a stable, hashable stand-in.
    return name, json.dumps(args, sort_keys=True, default=str)


class ToolRuntime:
    """Executes a batch of tool calls against a set of ``ToolSpec``s."""

    def __init__(
        self,
        specs: list[ToolSpec],
        *,
        cache_manager: CacheManager | None = None,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        progress_sink: ProgressSink | None = None,
        run_id: str | None = None,
        metrics_hook: Callable[[ToolRunMetric], None] | None = None,
    ) -> None:
        self._specs: dict[str, ToolSpec] = {spec.name: spec for spec in specs}
        self._cache_manager = cache_manager
        self._semaphore = asyncio.Semaphore(max(1, max_concurrency))
        self._progress_sink = progress_sink
        self._run_id = run_id
        self._metrics_hook = metrics_hook
        logger.info("Initialized tool runtime", tool_count=len(self._specs))

    def get_spec(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def get_tool(self, name: str) -> Tool | None:
        """``Tool`` view of one spec (via ``ToolSpec.to_legacy_tool``) — schema
        introspection call sites (``_openai_tool_definitions`` and friends)
        that pre-date ``ToolSpec`` read schemas this way; execution should go
        through ``run_batch``/``execute_tool``, not this."""
        spec = self._specs.get(name)
        return spec.to_legacy_tool() if spec is not None else None

    def list_tools(self) -> list[str]:
        return list(self._specs.keys())

    async def run_batch(
        self,
        calls: list[ToolCallRequest],
        *,
        deadline: float | None = None,
    ) -> list[ToolResult[Any]]:
        """Execute ``calls`` (order-preserving results), respecting ``deadline``
        (a ``time.monotonic()`` timestamp; a call that can't start before it is
        skipped rather than run).

        Parallel-safe calls run concurrently (bounded by ``max_concurrency``);
        any ``parallel_safe=False`` calls then run one at a time, in original
        order. This is a deliberate simplification — a non-parallel-safe call
        is not made mutually exclusive against the parallel group itself, only
        against other non-parallel-safe calls in the same batch. No tool in
        this codebase's bundles currently sets ``parallel_safe=False`` in a
        batch alongside calls it genuinely conflicts with; revisit with a real
        readers/writer lock if one ever does.
        """
        # Single-flight: identical (name, args) collapse onto one task.
        tasks: dict[int, asyncio.Task[ToolResult[Any]]] = {}
        dedupe_tasks: dict[tuple[str, str], asyncio.Task[ToolResult[Any]]] = {}

        parallel_indices: list[int] = []
        sequential_indices: list[int] = []
        for i, call in enumerate(calls):
            spec = self._specs.get(call.name)
            if spec is not None and spec.parallel_safe:
                parallel_indices.append(i)
            else:
                sequential_indices.append(i)

        def _schedule(i: int) -> asyncio.Task[ToolResult[Any]]:
            call = calls[i]
            key = _dedupe_key(call.name, call.args)
            existing = dedupe_tasks.get(key)
            if existing is not None:
                # A dedupe hit still gets its own started/finished progress
                # pair — the model asked for this specific call (its own
                # call_index/iteration), even though the underlying work is
                # shared with another position in the batch. Without this,
                # every position after the first silently drops off the
                # progress stream.
                return asyncio.ensure_future(self._await_deduped(call, existing))
            task = asyncio.ensure_future(self._execute_one(call, deadline=deadline))
            dedupe_tasks[key] = task
            return task

        for i in parallel_indices:
            tasks[i] = _schedule(i)
        if parallel_indices:
            await asyncio.gather(*(tasks[i] for i in parallel_indices))

        for i in sequential_indices:
            tasks[i] = _schedule(i)
            await tasks[i]

        return [tasks[i].result() for i in range(len(calls))]

    async def _await_deduped(
        self, call: ToolCallRequest, exec_task: asyncio.Task[ToolResult[Any]]
    ) -> ToolResult[Any]:
        await self._emit_started(call)
        t0 = time.monotonic()
        result = await exec_task
        await self._emit_finished(call, result, t0)
        return result

    async def execute_tool(self, name: str, **kwargs: Any) -> ToolResult[Any]:
        """Single-call convenience wrapper (no deadline, no batching) — for
        callers migrating one call site at a time off ``ToolExecutor``."""
        results = await self.run_batch([ToolCallRequest(name=name, args=kwargs)])
        return results[0]

    async def _execute_one(
        self, call: ToolCallRequest, *, deadline: float | None
    ) -> ToolResult[Any]:
        spec = self._specs.get(call.name)
        if spec is None:
            available = list(self._specs.keys())
            error_msg = f"Tool '{call.name}' not found. Available tools: {available}"
            logger.error("Tool not found", tool_name=call.name, available_tools=available)
            self._record_metric(call.name, 0.0, success=False)
            return ToolResult(success=False, data=None, error=error_msg)

        if deadline is not None and time.monotonic() >= deadline:
            logger.warning("Tool skipped: past wall-clock deadline", tool_name=call.name)
            self._record_metric(call.name, 0.0, success=False, skipped_reason="budget")
            return _skipped_result("budget")

        await self._emit_started(call)

        t0 = time.monotonic()
        cache_hit = False
        try:
            # Validate once, up front — the same validated args are used for
            # the cache key and the handler call, so e.g. {"symbol": "AAPL"}
            # and {"symbol": "AAPL", "interval": "1d"} (interval's own
            # schema default) hash identically instead of missing each other.
            validated_args = spec.args_model.model_validate(call.args).model_dump()

            cached = await self._cache_get(spec, validated_args)
            if cached is not None:
                cache_hit = True
                age_s = (datetime.now(UTC) - cached.cached_at).total_seconds()
                result: ToolResult[Any] = ToolResult(
                    success=True,
                    data=cached.data,
                    metadata={
                        **cached.metadata,
                        "cached": True,
                        "cached_at": cached.cached_at.isoformat(),
                        "cache_warning": f"Data cached {int(age_s // 60)} minutes ago.",
                    },
                )
            else:
                # The deadline check must happen AFTER acquiring the
                # semaphore, not before: computing `remaining` up front and
                # only entering the semaphore afterward means a long queue
                # wait for a concurrency slot goes uncounted against the
                # budget — a call could wait past the deadline for a slot
                # and then still get the tool's full timeout_s to run,
                # blowing the outer budget the semaphore wait was already
                # eating into.
                async with self._semaphore:
                    remaining = spec.timeout_s
                    if deadline is not None:
                        remaining = max(0.0, min(remaining, deadline - time.monotonic()))
                        if remaining <= 0:
                            self._record_metric(
                                call.name,
                                time.monotonic() - t0,
                                success=False,
                                skipped_reason="budget",
                            )
                            result = _skipped_result("budget")
                            await self._emit_finished(call, result, t0)
                            return result
                    result = await asyncio.wait_for(
                        spec.handler(**validated_args), timeout=remaining
                    )
                if result.success:
                    await self._cache_set(spec, validated_args, result)
        except TimeoutError:
            logger.warning("Tool timed out", tool_name=call.name, timeout_s=spec.timeout_s)
            result = ToolResult(
                success=False,
                data=None,
                error=f"Tool '{call.name}' timed out after {spec.timeout_s}s",
                metadata={"status": "timeout"},
            )
        except Exception as e:
            logger.error("Tool execution failed", tool_name=call.name, error=str(e))
            result = ToolResult(success=False, data=None, error=str(e))

        self._record_metric(
            call.name, time.monotonic() - t0, success=result.success, cache_hit=cache_hit
        )
        await self._emit_finished(call, result, t0)
        return result

    async def _cache_get(self, spec: ToolSpec, validated_args: dict[str, Any]) -> Any:
        if self._cache_manager is None or not spec.cache_ttl_s or not spec.cacheable:
            return None
        try:
            return await self._cache_manager.get(spec.name, **validated_args)
        except Exception:
            logger.warning("Tool cache read failed; proceeding without it", tool_name=spec.name)
            return None

    async def _cache_set(
        self, spec: ToolSpec, validated_args: dict[str, Any], result: ToolResult[Any]
    ) -> None:
        if self._cache_manager is None or not spec.cache_ttl_s or not spec.cacheable:
            return
        try:
            await self._cache_manager.set(
                spec.name,
                data=result.data,
                metadata=result.metadata,
                ttl=timedelta(seconds=spec.cache_ttl_s),
                **validated_args,
            )
        except Exception:
            logger.warning("Tool cache write failed; continuing without it", tool_name=spec.name)

    def _record_metric(
        self,
        tool_name: str,
        duration_s: float,
        *,
        success: bool,
        cache_hit: bool = False,
        skipped_reason: str | None = None,
    ) -> None:
        if self._metrics_hook is None:
            return
        try:
            self._metrics_hook(
                ToolRunMetric(
                    tool_name=tool_name,
                    duration_s=duration_s,
                    success=success,
                    cache_hit=cache_hit,
                    skipped_reason=skipped_reason,
                )
            )
        except Exception:
            logger.warning("metrics_hook raised; ignoring", tool_name=tool_name)

    async def _emit_started(self, call: ToolCallRequest) -> None:
        # A ProgressSink implementation that raises must never propagate from
        # here: this runs inside a task under asyncio.gather in run_batch,
        # and a bare gather neither cancels nor awaits sibling tasks when one
        # raises, leaking them.
        if self._progress_sink is None or self._run_id is None:
            return
        try:
            await maybe_emit_progress(
                self._progress_sink,
                ToolStartedEvent(
                    run_id=self._run_id,
                    tool_name=call.name,
                    args_summary=summarize_for_tool_args(call.args),
                    iteration=call.iteration,
                    call_index=call.call_index,
                ),
            )
        except Exception:
            logger.warning("progress_sink emit(started) failed; continuing", tool_name=call.name)

    async def _emit_finished(
        self, call: ToolCallRequest, result: ToolResult[Any], started_at: float
    ) -> None:
        if self._progress_sink is None or self._run_id is None:
            return
        duration_ms = (time.monotonic() - started_at) * 1000.0
        summary = summarize_tool_result(
            result.success, result.data, result.error if not result.success else None
        )
        try:
            await maybe_emit_progress(
                self._progress_sink,
                ToolFinishedEvent(
                    run_id=self._run_id,
                    tool_name=call.name,
                    success=result.success,
                    duration_ms=duration_ms,
                    result_summary=summary,
                ),
            )
        except Exception:
            logger.warning("progress_sink emit(finished) failed; continuing", tool_name=call.name)
