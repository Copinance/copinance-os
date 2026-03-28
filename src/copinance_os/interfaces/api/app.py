"""FastAPI application factory (minimal health + backtest endpoint)."""

from __future__ import annotations

from typing import Any

from copinance_os.core.orchestrator.research_orchestrator import ResearchOrchestrator
from copinance_os.core.orchestrator.run_job import DefaultJobRunner
from copinance_os.domain.backtest import SimpleBacktestResult
from copinance_os.research.workflows.backtest import SimpleLongOnlyWorkflowRequest

_FastAPI: Any = None
try:
    from fastapi import FastAPI as _FastAPI_cls

    _FastAPI = _FastAPI_cls
except ImportError:
    pass

# Stable public name for OpenAPI / clients
SimpleLongOnlyBacktestRequest = SimpleLongOnlyWorkflowRequest


def create_app(
    *,
    research_orchestrator: ResearchOrchestrator | None = None,
) -> Any:
    """Build FastAPI app. Requires ``fastapi`` to be installed.

    Pass ``research_orchestrator`` from the DI container in production; the default
    uses an empty executor list (backtest-only; analysis jobs would fail routing).
    """
    if _FastAPI is None:
        raise ImportError("FastAPI is required for the HTTP API. Install with: pip install fastapi")

    orch = research_orchestrator or ResearchOrchestrator(
        DefaultJobRunner(profile_repository=None, analysis_executors=[])
    )

    app = _FastAPI(
        title="Copinance OS API",
        version="0.1.0",
        description="Research OS API: health checks and deterministic backtest helpers.",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/backtest/simple-long-only", response_model=SimpleBacktestResult)
    def simple_long_only_backtest(payload: SimpleLongOnlyWorkflowRequest) -> SimpleBacktestResult:
        return orch.run_simple_long_only_backtest(payload)

    return app
