"""One-off workflow execution (no persistence)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from copinanceos.application.use_cases.base import UseCase
from copinanceos.domain.exceptions import DomainError, WorkflowNotFoundError
from copinanceos.domain.models.job import Job, JobScope, JobTimeframe
from copinanceos.domain.ports.repositories import ResearchProfileRepository
from copinanceos.domain.ports.workflows import WorkflowExecutor


class RunWorkflowRequest(BaseModel):
    """Request to run a workflow once without persisting."""

    scope: JobScope = Field(..., description="Scope (stock or market)")
    stock_symbol: str | None = None
    market_index: str | None = None
    timeframe: JobTimeframe = Field(..., description="Timeframe")
    workflow_type: str = Field(..., description="Workflow type (stock, macro, agent)")
    profile_id: UUID | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class RunWorkflowResponse(BaseModel):
    """Response from one-off workflow run."""

    success: bool
    results: dict[str, Any] | None
    error_message: str | None


class RunWorkflowUseCase(UseCase[RunWorkflowRequest, RunWorkflowResponse]):
    """Run a workflow once (no persistence). Used by analyze and ask CLI."""

    def __init__(
        self,
        profile_repository: ResearchProfileRepository | None,
        workflow_executors: list[WorkflowExecutor],
    ) -> None:
        self._profile_repository = profile_repository
        self._workflow_executors = workflow_executors

    async def _find_executor(self, job: Job) -> WorkflowExecutor:
        for executor in self._workflow_executors:
            if executor.get_workflow_type() == job.workflow_type:
                if await executor.validate(job):
                    return executor
        raise WorkflowNotFoundError(job.workflow_type)

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

    async def execute(self, request: RunWorkflowRequest) -> RunWorkflowResponse:
        job = Job(
            scope=request.scope,
            stock_symbol=request.stock_symbol,
            market_index=request.market_index,
            timeframe=request.timeframe,
            workflow_type=request.workflow_type,
            profile_id=request.profile_id,
            error_message=None,
        )
        executor = await self._find_executor(job)
        context = await self._build_context(job, request.context)
        try:
            results = await executor.execute(job, context)
            return RunWorkflowResponse(success=True, results=results, error_message=None)
        except DomainError as e:
            return RunWorkflowResponse(success=False, results=None, error_message=str(e))
        except Exception as e:
            return RunWorkflowResponse(
                success=False,
                results=None,
                error_message=f"Workflow execution failed: {e!s}",
            )
