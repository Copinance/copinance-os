"""Default job runner implementation.

Runs a single Job by finding an AnalysisExecutor that validates for it,
building context (e.g. profile), and calling executor.execute(job, context).
Consumers can replace this with their own JobRunner (queue-based, custom routing).
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, unbind_contextvars

from copinance_os.domain.exceptions import (
    DataProviderUnavailableError,
    DomainError,
    ExecutorNotFoundError,
    RetryableExecutionError,
)
from copinance_os.domain.literacy import resolve_financial_literacy
from copinance_os.domain.models.job import Job, ReportExclusionReason, RunJobResult
from copinance_os.domain.ports.analysis_execution import AnalysisExecutor, JobRunner
from copinance_os.domain.ports.repositories import AnalysisProfileRepository
from copinance_os.domain.services.run_job_analysis_report import build_run_job_analysis_report

logger = structlog.get_logger(__name__)

_REPORT_ENVELOPE_EXECUTION_TYPES = frozenset(
    {"instrument_analysis", "market_analysis", "question_driven_analysis"}
)

_DEFAULT_RETRYABLE: tuple[type[BaseException], ...] = (
    RetryableExecutionError,
    DataProviderUnavailableError,
)


class DefaultJobRunner(JobRunner):
    """Default implementation: find executor for job, build context, execute."""

    def __init__(
        self,
        profile_repository: AnalysisProfileRepository | None,
        analysis_executors: list[AnalysisExecutor],
        *,
        max_execute_retries: int = 0,
        retryable_exceptions: tuple[type[BaseException], ...] | None = None,
    ) -> None:
        self._profile_repository = profile_repository
        self._analysis_executors = analysis_executors
        self._max_execute_retries = max(0, max_execute_retries)
        self._retryable_exceptions = retryable_exceptions or _DEFAULT_RETRYABLE

    async def _find_executor(self, job: Job) -> AnalysisExecutor:
        for executor in self._analysis_executors:
            if await executor.validate(job):
                return executor
        raise ExecutorNotFoundError(job.execution_type)

    async def _build_context(self, job: Job, base: dict[str, Any]) -> dict[str, Any]:
        out = dict(base)
        if job.profile_id and self._profile_repository:
            profile = await self._profile_repository.get_by_id(job.profile_id)
            if profile:
                # Request-level financial_literacy takes precedence over profile value
                if "financial_literacy" not in out:
                    out["financial_literacy"] = profile.financial_literacy.value
                out["profile_preferences"] = profile.preferences
                if profile.display_name:
                    out["profile_display_name"] = profile.display_name
        if "financial_literacy" not in out:
            logger.warning(
                "financial_literacy not in context and no profile attached; defaulting to intermediate",
                execution_type=job.execution_type,
            )
        return out

    async def run(self, job: Job, context: dict[str, Any]) -> RunJobResult:
        executor = await self._find_executor(job)
        ctx = await self._build_context(job, context)
        run_id = context.get("run_id")
        if run_id is not None:
            bind_contextvars(run_id=str(run_id), job_execution_type=job.execution_type)
        logger.info(
            "job_run_start",
            execution_type=job.execution_type,
            scope=job.scope.value,
        )
        try:
            for attempt in range(self._max_execute_retries + 1):
                try:
                    results = await executor.execute(job, ctx)
                    lit = resolve_financial_literacy(ctx.get("financial_literacy"))
                    report = build_run_job_analysis_report(results, lit) if results else None
                    report_exclusion: ReportExclusionReason | None = None
                    if results and report is None:
                        et = results.get("execution_type")
                        if et and et not in _REPORT_ENVELOPE_EXECUTION_TYPES:
                            report_exclusion = ReportExclusionReason.UNKNOWN_EXECUTOR_TYPE
                    logger.info(
                        "job_run_success",
                        execution_type=job.execution_type,
                        attempt=attempt,
                    )
                    return RunJobResult(
                        success=True,
                        results=results,
                        error_message=None,
                        report=report,
                        report_exclusion_reason=report_exclusion,
                    )
                except DomainError as e:
                    if attempt < self._max_execute_retries and isinstance(
                        e, self._retryable_exceptions
                    ):
                        delay = 0.5 * (2**attempt)
                        logger.warning(
                            "job_execute_retry",
                            execution_type=job.execution_type,
                            attempt=attempt + 1,
                            max_attempts=self._max_execute_retries + 1,
                            delay_s=delay,
                            error=str(e),
                        )
                        await asyncio.sleep(delay)
                        continue
                    return RunJobResult(success=False, results=None, error_message=str(e))
                except Exception as e:
                    return RunJobResult(
                        success=False,
                        results=None,
                        error_message=f"Analysis execution failed: {e!s}",
                    )
            raise RuntimeError("job run loop exited without result")
        finally:
            if run_id is not None:
                unbind_contextvars("run_id", "job_execution_type")
