"""Unit tests for analyze CLI commands."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copinanceos.cli.analyze import analyze_equity, analyze_macro
from copinanceos.domain.models.job import JobScope, JobTimeframe
from copinanceos.domain.models.market import MarketType


@pytest.mark.unit
class TestAnalyzeCLI:
    @patch("copinanceos.cli.analyze.ensure_profile_with_literacy")
    @patch("copinanceos.cli.analyze.container.job_runner")
    @patch("copinanceos.cli.analyze.console")
    def test_analyze_equity_runs_workflow_without_persisting(
        self,
        mock_console: MagicMock,
        mock_job_runner: MagicMock,
        mock_ensure_profile: MagicMock,
    ) -> None:
        mock_ensure_profile.return_value = None
        mock_runner = AsyncMock()
        mock_runner.run = AsyncMock(
            return_value=MagicMock(success=True, results={"summary": "ok"}, error_message=None)
        )
        mock_job_runner.return_value = mock_runner

        analyze_equity(symbol="AAPL", timeframe=JobTimeframe.MID_TERM, profile_id=None)

        job = mock_runner.run.call_args[0][0]
        assert job.scope == JobScope.INSTRUMENT
        assert job.market_type == MarketType.EQUITY
        assert job.instrument_symbol == "AAPL"
        assert job.workflow_type == "equity"
        assert mock_console.print.called

    @patch("copinanceos.cli.analyze.container.job_runner")
    @patch("copinanceos.cli.analyze.console")
    def test_analyze_macro_runs_workflow_without_persisting(
        self,
        mock_console: MagicMock,
        mock_job_runner: MagicMock,
    ) -> None:
        mock_runner = AsyncMock()
        mock_runner.run = AsyncMock(
            return_value=MagicMock(
                success=True, results={"macro": {"available": True}}, error_message=None
            )
        )
        mock_job_runner.return_value = mock_runner

        analyze_macro(market_index="SPY", lookback_days=90)

        job = mock_runner.run.call_args[0][0]
        context = mock_runner.run.call_args[0][1]
        assert job.scope == JobScope.MARKET
        assert job.market_index == "SPY"
        assert job.workflow_type == "macro"
        assert context["market_index"] == "SPY"
        assert context["lookback_days"] == 90
        assert mock_console.print.called
