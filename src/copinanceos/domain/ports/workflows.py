"""Workflow execution interfaces."""

from abc import ABC, abstractmethod
from typing import Any

from copinanceos.domain.models.job import Job, RunJobResult


class JobRunner(ABC):
    """Port for running a single job. Consumers can use the library's default
    implementation or provide their own (e.g. queue-based, custom routing).
    """

    @abstractmethod
    async def run(self, job: Job, context: dict[str, Any]) -> RunJobResult:
        """Run the job with the given context. Returns success, results, and optional error."""
        pass


class WorkflowExecutor(ABC):
    """Abstract interface for workflow execution (stock, macro, or agent)."""

    @abstractmethod
    async def execute(self, job: Job, context: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a workflow for the given job.

        Args:
            job: The job to execute
            context: Execution context and parameters

        Returns:
            Results dictionary containing workflow outputs
        """
        pass

    @abstractmethod
    async def validate(self, job: Job) -> bool:
        """
        Validate if this executor can handle the given job.

        Args:
            job: The job to validate

        Returns:
            True if executor can handle this job
        """
        pass

    @abstractmethod
    def get_workflow_type(self) -> str:
        """Get the workflow type identifier."""
        pass
