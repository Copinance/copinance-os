"""Analyze use cases: analysis runner ports and use cases (orchestration layer)."""

from __future__ import annotations

# Re-export routing helpers and request types for consumers that import from this module
from copinance_os.domain.models.analysis import (  # noqa: F401
    INSTRUMENT_DETERMINISTIC_TYPE,
    INSTRUMENT_QUESTION_DRIVEN_TYPE,
    MARKET_DETERMINISTIC_TYPE,
    MARKET_QUESTION_DRIVEN_TYPE,
    AnalyzeInstrumentRequest,
    AnalyzeMarketRequest,
    AnalyzeMode,
    execution_type_from_scope_and_mode,
    get_default_instrument_timeframe,
    resolve_analyze_mode,
)
from copinance_os.domain.models.job import RunJobResult
from copinance_os.domain.ports.analysis_execution import (
    AnalyzeInstrumentRunner,
    AnalyzeMarketRunner,
)
from copinance_os.research.workflows.base import UseCase


class AnalyzeInstrumentUseCase(UseCase[AnalyzeInstrumentRequest, RunJobResult]):
    """Analyze an instrument using deterministic or question-driven execution."""

    def __init__(self, analyze_instrument_runner: AnalyzeInstrumentRunner) -> None:
        self._runner = analyze_instrument_runner

    async def execute(self, request: AnalyzeInstrumentRequest) -> RunJobResult:
        return await self._runner.run(request)


class AnalyzeMarketUseCase(UseCase[AnalyzeMarketRequest, RunJobResult]):
    """Analyze the broader market using deterministic or question-driven execution."""

    def __init__(self, analyze_market_runner: AnalyzeMarketRunner) -> None:
        self._runner = analyze_market_runner

    async def execute(self, request: AnalyzeMarketRequest) -> RunJobResult:
        return await self._runner.run(request)
