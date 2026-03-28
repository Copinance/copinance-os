"""Simple long-only backtest via ResearchOrchestrator."""

import pytest

from copinance_os.core.orchestrator.research_orchestrator import ResearchOrchestrator
from copinance_os.core.orchestrator.run_job import DefaultJobRunner
from copinance_os.research.workflows.backtest import SimpleLongOnlyWorkflowRequest


@pytest.mark.unit
def test_workflow_matches_direct_execution() -> None:
    orch = ResearchOrchestrator(DefaultJobRunner(profile_repository=None, analysis_executors=[]))
    req = SimpleLongOnlyWorkflowRequest(
        closes=[100.0, 110.0, 121.0],
        weights=[1.0, 1.0, 1.0],
        strategy_id="test",
        initial_cash=1000.0,
    )
    out = orch.run_simple_long_only_backtest(req)
    assert out.equity_curve[-1] == pytest.approx(1210.0)


@pytest.mark.unit
def test_workflow_rejects_misaligned_weights() -> None:
    with pytest.raises(ValueError, match="same length"):
        SimpleLongOnlyWorkflowRequest(
            closes=[1.0, 2.0],
            weights=[1.0],
            strategy_id="x",
        )
