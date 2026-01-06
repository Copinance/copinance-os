"""Workflow execution interfaces."""

from abc import ABC, abstractmethod
from typing import Any

from copinanceos.domain.models.research import Research


class WorkflowExecutor(ABC):
    """Abstract interface for workflow execution (stock, macro, or agent)."""

    @abstractmethod
    async def execute(self, research: Research, context: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a workflow for the given research.

        Args:
            research: The research entity to execute
            context: Execution context and parameters

        Returns:
            Results dictionary containing workflow outputs
        """
        pass

    @abstractmethod
    async def validate(self, research: Research) -> bool:
        """
        Validate if this executor can handle the given research.

        Args:
            research: The research entity to validate

        Returns:
            True if executor can handle this research
        """
        pass

    @abstractmethod
    def get_workflow_type(self) -> str:
        """Get the workflow type identifier."""
        pass
