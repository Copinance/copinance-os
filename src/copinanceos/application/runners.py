"""Default runners for progressive analyze execution (build Job from request, delegate to JobRunner)."""

from __future__ import annotations

from typing import Any

from copinanceos.application.use_cases.analyze import (
    AnalyzeInstrumentRequest,
    AnalyzeInstrumentRunner,
    AnalyzeMarketRequest,
    AnalyzeMarketRunner,
    execution_type_from_scope_and_mode,
    get_default_instrument_timeframe,
    resolve_analyze_mode,
)
from copinanceos.domain.models.job import Job, JobScope, RunJobResult
from copinanceos.domain.ports.analysis_execution import JobRunner


class DefaultAnalyzeInstrumentRunner(AnalyzeInstrumentRunner):
    """Build an instrument job and delegate to JobRunner."""

    def __init__(self, job_runner: JobRunner) -> None:
        self._job_runner = job_runner

    async def run(self, request: AnalyzeInstrumentRequest) -> RunJobResult:
        resolved_mode = resolve_analyze_mode(request.mode, request.question)
        execution_type = execution_type_from_scope_and_mode(JobScope.INSTRUMENT, resolved_mode)
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=request.market_type,
            instrument_symbol=request.symbol,
            market_index=None,
            timeframe=request.timeframe or get_default_instrument_timeframe(request.market_type),
            execution_type=execution_type,
            profile_id=request.profile_id,
            error_message=None,
        )
        context: dict[str, Any] = {
            "question": request.question,
            "market_type": request.market_type.value,
            "expiration_date": request.expiration_date,
            "option_side": request.option_side.value,
            "include_prompt": request.include_prompt_in_results,
        }
        return await self._job_runner.run(job, context)


class DefaultAnalyzeMarketRunner(AnalyzeMarketRunner):
    """Build a market job and delegate to JobRunner."""

    def __init__(self, job_runner: JobRunner) -> None:
        self._job_runner = job_runner

    async def run(self, request: AnalyzeMarketRequest) -> RunJobResult:
        resolved_mode = resolve_analyze_mode(request.mode, request.question)
        execution_type = execution_type_from_scope_and_mode(JobScope.MARKET, resolved_mode)
        job = Job(
            scope=JobScope.MARKET,
            market_type=None,
            instrument_symbol=None,
            market_index=request.market_index,
            timeframe=request.timeframe,
            execution_type=execution_type,
            profile_id=request.profile_id,
            error_message=None,
        )
        context: dict[str, Any] = {
            "question": request.question,
            "include_prompt": request.include_prompt_in_results,
            "market_index": request.market_index,
            "lookback_days": request.lookback_days,
            "include_vix": request.include_vix,
            "include_market_breadth": request.include_market_breadth,
            "include_sector_rotation": request.include_sector_rotation,
            "include_rates": request.include_rates,
            "include_credit": request.include_credit,
            "include_commodities": request.include_commodities,
            "include_labor": request.include_labor,
            "include_housing": request.include_housing,
            "include_manufacturing": request.include_manufacturing,
            "include_consumer": request.include_consumer,
            "include_global": request.include_global,
            "include_advanced": request.include_advanced,
        }
        return await self._job_runner.run(job, context)
