"""Default job runner implementation.

Runs a single Job by finding an AnalysisExecutor that validates for it,
building context (e.g. profile), and calling executor.execute(job, context).
Consumers can replace this with their own JobRunner (queue-based, custom routing).
"""

from __future__ import annotations

from typing import Any

from copinanceos.domain.exceptions import DomainError, ExecutorNotFoundError
from copinanceos.domain.models.job import Job, RunJobResult
from copinanceos.domain.ports.analysis_execution import AnalysisExecutor, JobRunner
from copinanceos.domain.ports.repositories import AnalysisProfileRepository


class DefaultJobRunner(JobRunner):
    """Default implementation: find executor for job, build context, execute."""

    def __init__(
        self,
        profile_repository: AnalysisProfileRepository | None,
        analysis_executors: list[AnalysisExecutor],
    ) -> None:
        self._profile_repository = profile_repository
        self._analysis_executors = analysis_executors

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
                out["financial_literacy"] = profile.financial_literacy.value
                out["profile_preferences"] = profile.preferences
                if profile.display_name:
                    out["profile_display_name"] = profile.display_name
        return out

    async def run(self, job: Job, context: dict[str, Any]) -> RunJobResult:
        executor = await self._find_executor(job)
        ctx = await self._build_context(job, context)
        try:
            results = await executor.execute(job, ctx)
            return RunJobResult(success=True, results=results, error_message=None)
        except DomainError as e:
            return RunJobResult(success=False, results=None, error_message=str(e))
        except Exception as e:
            return RunJobResult(
                success=False,
                results=None,
                error_message=f"Analysis execution failed: {e!s}",
            )
