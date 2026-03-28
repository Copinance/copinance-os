"""Single entry point for research execution: analysis jobs and deterministic workflows.

All library and interface code should use ``ResearchOrchestrator`` rather than calling
``JobRunner`` or domain backtest functions directly (convention: orchestration is mandatory).
"""

from __future__ import annotations

from typing import Any

from copinance_os.core.execution_engine.backtest import execute_simple_long_only_backtest
from copinance_os.domain.backtest import SimpleBacktestConfig, SimpleBacktestResult
from copinance_os.domain.models.job import Job, RunJobResult
from copinance_os.domain.ports.analysis_execution import JobRunner
from copinance_os.domain.strategies.signal import StrategySignal
from copinance_os.research.workflows.backtest import SimpleLongOnlyWorkflowRequest


class ResearchOrchestrator:
    """Facades ``JobRunner`` and workflow execution behind one orchestration API."""

    def __init__(self, job_runner: JobRunner) -> None:
        self._job_runner = job_runner

    async def run_job(self, job: Job, context: dict[str, Any]) -> RunJobResult:
        """Run a routed analysis job (instrument / market / question-driven)."""
        return await self._job_runner.run(job, context)

    def run_simple_long_only_backtest(
        self, request: SimpleLongOnlyWorkflowRequest
    ) -> SimpleBacktestResult:
        """Validate ``StrategySignal`` contract and run the execution-layer backtest.

        For YAML/JSON-driven runs, use
        ``copinance_os.research.workflows.backtest_config.load_simple_long_only_workflow_request``
        or ``run_simple_long_only_from_config_file``.
        """
        StrategySignal(strategy_id=request.strategy_id, weights=request.weights)
        cfg = SimpleBacktestConfig(
            initial_cash=request.initial_cash,
            commission_bps=request.commission_bps,
            slippage_bps=request.slippage_bps,
            trading_days_per_year=request.trading_days_per_year,
        )
        return execute_simple_long_only_backtest(request.closes, request.weights, cfg)
