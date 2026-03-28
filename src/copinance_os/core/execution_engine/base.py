"""Base analysis executor with common execution patterns."""

from abc import abstractmethod
from datetime import UTC, datetime
from typing import Any

import structlog

from copinance_os.domain.models.job import Job, JobScope
from copinance_os.domain.ports.analysis_execution import AnalysisExecutor

logger = structlog.get_logger(__name__)


class BaseAnalysisExecutor(AnalysisExecutor):
    """Base class with common analysis execution logic.

    Provides a template method pattern for execution with:
    - Common result initialization
    - Logging setup and teardown
    - Error handling
    - Status management

    Subclasses implement `_execute_analysis()` to provide specific logic.
    """

    @abstractmethod
    def get_executor_id(self) -> str:
        """Return the executor identifier used for routing."""
        pass

    @abstractmethod
    async def validate(self, job: Job) -> bool:
        """Validate if this executor can handle the given job."""
        pass

    @abstractmethod
    async def _execute_analysis(self, job: Job, context: dict[str, Any]) -> dict[str, Any]:
        """Execute the specific analysis logic. Subclasses implement this."""
        pass

    async def execute(self, job: Job, context: dict[str, Any]) -> dict[str, Any]:
        """Execute analysis with common setup, error handling, and logging."""
        target_symbol = (
            job.market_index if job.scope == JobScope.MARKET else (job.instrument_symbol or None)
        )
        target_symbol = target_symbol.upper() if isinstance(target_symbol, str) else "N/A"
        timeframe = job.timeframe.value
        execution_type = self.get_executor_id()

        results = self._initialize_results(job, execution_type)

        logger.info(
            "Starting analysis execution",
            execution_type=execution_type,
            symbol=target_symbol,
            timeframe=timeframe,
        )

        try:
            analysis_results = await self._execute_analysis(job, context)

            if hasattr(analysis_results, "model_dump"):
                results.update(analysis_results.model_dump())
            else:
                results.update(analysis_results)

            if hasattr(self, "_post_process_result"):
                results = self._post_process_result(results)

            if "status" not in results:
                results["status"] = "completed"
                if "message" not in results:
                    results["message"] = "Analysis executed successfully"
            elif results.get("status") is None:
                pass
            elif "message" not in results:
                results["message"] = "Analysis executed successfully"

            logger.info(
                "Analysis execution completed",
                execution_type=execution_type,
                symbol=target_symbol,
                timeframe=timeframe,
            )

        except Exception as e:
            logger.error(
                "Analysis execution failed",
                execution_type=execution_type,
                symbol=target_symbol,
                error=str(e),
                exc_info=True,
            )
            results["status"] = "failed"
            results["error"] = str(e)
            results["message"] = f"Analysis execution failed: {str(e)}"

        return results

    def _initialize_results(self, job: Job, execution_type: str) -> dict[str, Any]:
        """Initialize common result structure."""
        execution_mode = (
            "question_driven" if "question_driven" in job.execution_type else "deterministic"
        )
        return {
            "execution_type": execution_type,
            "scope": job.scope.value,
            "market_type": job.market_type.value if job.market_type else None,
            "instrument_symbol": job.instrument_symbol,
            "market_index": job.market_index,
            "timeframe": job.timeframe.value,
            "execution_mode": execution_mode,
            "execution_timestamp": datetime.now(UTC).isoformat(),
        }
