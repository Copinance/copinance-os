"""Job and analysis execution interfaces."""

from abc import ABC, abstractmethod
from typing import Any

# Forward reference resolved at import time — analysis models live in domain
from copinance_os.domain.models.analysis import AnalyzeInstrumentRequest, AnalyzeMarketRequest
from copinance_os.domain.models.job import Job, RunJobResult


class JobRunner(ABC):
    """Port for running a single job. Consumers can use the library's default
    implementation or provide their own (e.g. queue-based, custom routing).
    """

    @abstractmethod
    async def run(self, job: Job, context: dict[str, Any]) -> RunJobResult:
        """Run the job with the given context. Returns success, results, and optional error."""
        pass


class AnalysisExecutor(ABC):
    """Abstract interface for analysis execution (deterministic or question-driven)."""

    @abstractmethod
    async def execute(self, job: Job, context: dict[str, Any]) -> dict[str, Any]:
        """
        Execute analysis for the given job.

        Args:
            job: The job to execute
            context: Execution context and parameters

        Returns:
            Results dictionary containing analysis outputs
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
    def get_executor_id(self) -> str:
        """Return the executor identifier used for routing (e.g. deterministic_instrument_analysis)."""
        pass


class AnalyzeInstrumentRunner(ABC):
    """Port for progressive instrument analysis execution."""

    @abstractmethod
    async def run(self, request: AnalyzeInstrumentRequest) -> RunJobResult:
        """Run the instrument analysis."""
        pass


class AnalyzeMarketRunner(ABC):
    """Port for progressive market analysis execution."""

    @abstractmethod
    async def run(self, request: AnalyzeMarketRequest) -> RunJobResult:
        """Run the market analysis."""
        pass
