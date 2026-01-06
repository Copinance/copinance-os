"""Research-related use cases."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from copinanceos.application.use_cases.base import UseCase
from copinanceos.domain.exceptions import (
    DomainError,
    ProfileNotFoundError,
    ResearchNotFoundError,
    WorkflowExecutionError,
    WorkflowNotFoundError,
)
from copinanceos.domain.models.research import Research, ResearchStatus, ResearchTimeframe
from copinanceos.domain.ports.repositories import (
    ResearchProfileRepository,
    ResearchRepository,
)
from copinanceos.domain.ports.workflows import WorkflowExecutor


class CreateResearchRequest(BaseModel):
    """Request to create a new research."""

    stock_symbol: str = Field(..., description="Stock symbol to research")
    timeframe: ResearchTimeframe = Field(..., description="Research timeframe")
    workflow_type: str = Field(..., description="Workflow type (stock, macro, or agent)")
    parameters: dict[str, str] = Field(default_factory=dict, description="Research parameters")
    profile_id: UUID | None = Field(None, description="Optional research profile ID for context")


class CreateResearchResponse(BaseModel):
    """Response from creating a research."""

    research: Research = Field(..., description="Created research entity")


class CreateResearchUseCase(UseCase[CreateResearchRequest, CreateResearchResponse]):
    """Use case for creating a new research."""

    def __init__(self, research_repository: ResearchRepository) -> None:
        """Initialize use case."""
        self._research_repository = research_repository

    async def execute(self, request: CreateResearchRequest) -> CreateResearchResponse:
        """Execute the create research use case."""
        research = Research(
            stock_symbol=request.stock_symbol,
            timeframe=request.timeframe,
            workflow_type=request.workflow_type,
            parameters=request.parameters,
            profile_id=request.profile_id,
            error_message=None,
        )

        saved_research = await self._research_repository.save(research)
        return CreateResearchResponse(research=saved_research)


class GetResearchRequest(BaseModel):
    """Request to get a research by ID."""

    research_id: UUID = Field(..., description="Research ID to retrieve")


class GetResearchResponse(BaseModel):
    """Response from getting a research."""

    research: Research | None = Field(..., description="Research entity if found")


class GetResearchUseCase(UseCase[GetResearchRequest, GetResearchResponse]):
    """Use case for retrieving a research by ID."""

    def __init__(self, research_repository: ResearchRepository) -> None:
        """Initialize use case."""
        self._research_repository = research_repository

    async def execute(self, request: GetResearchRequest) -> GetResearchResponse:
        """Execute the get research use case."""
        research = await self._research_repository.get_by_id(request.research_id)
        return GetResearchResponse(research=research)


class ExecuteResearchRequest(BaseModel):
    """Request to execute a research workflow."""

    research_id: UUID = Field(..., description="Research ID to execute")
    context: dict[str, Any] = Field(default_factory=dict, description="Execution context")


class ExecuteResearchResponse(BaseModel):
    """Response from executing a research."""

    research: Research = Field(..., description="Updated research with results")
    success: bool = Field(..., description="Whether execution was successful")


class SetResearchContextRequest(BaseModel):
    """Request to set research context (profile)."""

    research_id: UUID = Field(..., description="Research ID to update")
    profile_id: UUID | None = Field(None, description="Research profile ID to set as context")


class SetResearchContextResponse(BaseModel):
    """Response from setting research context."""

    research: Research = Field(..., description="Updated research entity with context")


class SetResearchContextUseCase(UseCase[SetResearchContextRequest, SetResearchContextResponse]):
    """Use case for setting research context (profile)."""

    def __init__(
        self,
        research_repository: ResearchRepository,
        profile_repository: ResearchProfileRepository,
    ) -> None:
        """Initialize use case."""
        self._research_repository = research_repository
        self._profile_repository = profile_repository

    async def _validate_research_exists(self, research_id: UUID) -> Research:
        """Validate that a research exists.

        Args:
            research_id: Research ID to validate

        Returns:
            Research entity if found

        Raises:
            ResearchNotFoundError: If research does not exist
        """
        research = await self._research_repository.get_by_id(research_id)
        if research is None:
            raise ResearchNotFoundError(str(research_id))
        return research

    async def execute(self, request: SetResearchContextRequest) -> SetResearchContextResponse:
        """Execute the set research context use case."""
        research = await self._validate_research_exists(request.research_id)

        # Validate profile exists if provided
        if request.profile_id is not None:
            profile = await self._profile_repository.get_by_id(request.profile_id)
            if profile is None:
                raise ProfileNotFoundError(str(request.profile_id))

        # Update research with profile context
        research.profile_id = request.profile_id
        updated_research = await self._research_repository.save(research)
        return SetResearchContextResponse(research=updated_research)


class ExecuteResearchUseCase(UseCase[ExecuteResearchRequest, ExecuteResearchResponse]):
    """Use case for executing a research workflow."""

    def __init__(
        self,
        research_repository: ResearchRepository,
        profile_repository: ResearchProfileRepository | None,
        workflow_executors: list[WorkflowExecutor],
    ) -> None:
        """Initialize use case."""
        self._research_repository = research_repository
        self._profile_repository = profile_repository
        self._workflow_executors = workflow_executors

    async def _get_research(self, research_id: UUID) -> Research:
        """Get research by ID.

        Args:
            research_id: Research ID

        Returns:
            Research entity

        Raises:
            ResearchNotFoundError: If research does not exist
        """
        research = await self._research_repository.get_by_id(research_id)
        if research is None:
            raise ResearchNotFoundError(str(research_id))
        return research

    async def _mark_research_in_progress(self, research: Research) -> Research:
        """Mark research as in progress.

        Args:
            research: Research entity to update

        Returns:
            Updated research entity
        """
        research.status = ResearchStatus.IN_PROGRESS
        return await self._research_repository.save(research)

    async def _mark_research_completed(
        self, research: Research, results: dict[str, Any]
    ) -> Research:
        """Mark research as completed with results.

        Args:
            research: Research entity to update
            results: Workflow execution results

        Returns:
            Updated research entity
        """
        research.results = results
        research.status = ResearchStatus.COMPLETED
        return await self._research_repository.save(research)

    async def _mark_research_failed(self, research: Research, error_message: str) -> Research:
        """Mark research as failed with error message.

        Args:
            research: Research entity to update
            error_message: Error message describing the failure

        Returns:
            Updated research entity
        """
        research.error_message = error_message
        research.status = ResearchStatus.FAILED
        return await self._research_repository.save(research)

    async def _find_executor(
        self, research: Research, executors: list[WorkflowExecutor]
    ) -> WorkflowExecutor:
        """Find the appropriate workflow executor for a research.

        Args:
            research: Research entity to find executor for
            executors: List of available workflow executors

        Returns:
            Workflow executor that can handle this research

        Raises:
            WorkflowNotFoundError: If no executor is found for the workflow type
        """
        for executor in executors:
            if executor.get_workflow_type() == research.workflow_type:
                if await executor.validate(research):
                    return executor

        raise WorkflowNotFoundError(research.workflow_type)

    async def _build_execution_context(
        self, research: Research, base_context: dict[str, Any]
    ) -> dict[str, Any]:
        """Build execution context for research workflow.

        Merges profile data into the base context if a profile is associated
        with the research.

        Args:
            research: Research entity
            base_context: Base execution context

        Returns:
            Execution context with profile data merged in
        """
        execution_context = dict(base_context)

        if research.profile_id is not None and self._profile_repository is not None:
            profile = await self._profile_repository.get_by_id(research.profile_id)
            if profile is not None:
                # Merge profile data into execution context
                execution_context["financial_literacy"] = profile.financial_literacy.value
                execution_context["profile_preferences"] = profile.preferences
                if profile.display_name:
                    execution_context["profile_display_name"] = profile.display_name

        return execution_context

    async def execute(self, request: ExecuteResearchRequest) -> ExecuteResearchResponse:
        """Execute the research workflow use case."""
        # Get research
        research = await self._get_research(request.research_id)

        # Find appropriate executor
        executor = await self._find_executor(research, self._workflow_executors)

        # Build execution context
        execution_context = await self._build_execution_context(research, request.context)

        # Mark research as in progress
        research = await self._mark_research_in_progress(research)

        # Execute workflow
        try:
            results = await executor.execute(research, execution_context)
            research = await self._mark_research_completed(research, results)
            success = True
        except DomainError as domain_error:
            # Domain exceptions are business logic errors - wrap in WorkflowExecutionError
            workflow_error = WorkflowExecutionError(
                workflow_type=research.workflow_type,
                message=str(domain_error),
                research_id=str(research.id),
                details=domain_error.details,
            )
            research = await self._mark_research_failed(research, workflow_error.message)
            success = False
        except Exception as infrastructure_error:
            # Mark research as failed with the error message
            error_message = f"Workflow execution failed: {str(infrastructure_error)}"
            research = await self._mark_research_failed(research, error_message)
            success = False

        return ExecuteResearchResponse(research=research, success=success)
