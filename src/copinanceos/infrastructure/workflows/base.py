"""Base workflow executor with common execution patterns."""

from abc import abstractmethod
from datetime import UTC, datetime
from typing import Any

import structlog

from copinanceos.domain.models.research import Research
from copinanceos.domain.ports.workflows import WorkflowExecutor

logger = structlog.get_logger(__name__)


class BaseWorkflowExecutor(WorkflowExecutor):
    """Base class with common workflow execution logic.

    Provides a template method pattern for workflow execution with:
    - Common result initialization
    - Logging setup and teardown
    - Error handling
    - Status management

    Subclasses implement `_execute_workflow()` to provide specific workflow logic.
    """

    @abstractmethod
    def get_workflow_type(self) -> str:
        """Get the workflow type identifier."""
        pass

    @abstractmethod
    async def validate(self, research: Research) -> bool:
        """Validate if this executor can handle the given research."""
        pass

    @abstractmethod
    async def _execute_workflow(
        self, research: Research, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute the specific workflow logic.

        Subclasses implement this method to provide their specific workflow execution.

        Args:
            research: The research entity to execute
            context: Execution context and parameters

        Returns:
            Results dictionary containing workflow-specific outputs
        """
        pass

    async def execute(self, research: Research, context: dict[str, Any]) -> dict[str, Any]:
        """Execute a workflow with common setup, error handling, and logging.

        This method provides the template for workflow execution:
        1. Initialize common result structure
        2. Log execution start
        3. Execute workflow-specific logic
        4. Handle errors
        5. Log execution completion

        Args:
            research: The research entity to execute
            context: Execution context and parameters

        Returns:
            Results dictionary containing workflow outputs
        """
        symbol = research.stock_symbol.upper()
        timeframe = research.timeframe.value
        workflow_type = self.get_workflow_type()

        # Initialize common result structure
        results = self._initialize_results(research, workflow_type)

        # Log execution start
        logger.info(
            f"Starting {workflow_type} workflow execution",
            symbol=symbol,
            timeframe=timeframe,
        )

        try:
            # Execute workflow-specific logic
            workflow_results = await self._execute_workflow(research, context)

            # Handle both dictionary and Pydantic model returns
            if hasattr(workflow_results, "model_dump"):
                # Pydantic model - convert to dict and merge
                workflow_dict = workflow_results.model_dump()
                results.update(workflow_dict)
            else:
                # Dictionary - merge directly
                results.update(workflow_results)

            # Allow workflows to post-process the result (e.g., remove irrelevant fields)
            if hasattr(self, "_post_process_result"):
                results = self._post_process_result(results)

            # Ensure status is set
            if "status" not in results:
                results["status"] = "completed"
                # Add message for newly set status
                if "message" not in results:
                    results["message"] = (
                        f"{workflow_type.capitalize()} workflow executed successfully"
                    )
            elif results.get("status") is None:
                # If workflow explicitly set status to None, don't add message
                # This allows workflows to return clean output without status/message
                pass
            elif "message" not in results:
                # Only add message if status is not None
                results["message"] = f"{workflow_type.capitalize()} workflow executed successfully"

            # Log successful completion
            logger.info(
                f"{workflow_type.capitalize()} workflow execution completed",
                symbol=symbol,
                timeframe=timeframe,
            )

        except Exception as e:
            # Handle errors consistently
            logger.error(
                f"{workflow_type.capitalize()} workflow execution failed",
                symbol=symbol,
                error=str(e),
                exc_info=True,
            )
            results["status"] = "failed"
            results["error"] = str(e)
            results["message"] = f"{workflow_type.capitalize()} workflow execution failed: {str(e)}"

        return results

    def _initialize_results(self, research: Research, workflow_type: str) -> dict[str, Any]:
        """Initialize common result structure.

        Args:
            research: The research entity
            workflow_type: Type of workflow

        Returns:
            Dictionary with common result fields initialized
        """
        return {
            "workflow_type": workflow_type,
            "stock_symbol": research.stock_symbol.upper(),
            "timeframe": research.timeframe.value,
            "analysis_type": workflow_type,
            "execution_timestamp": datetime.now(UTC).isoformat(),
        }
