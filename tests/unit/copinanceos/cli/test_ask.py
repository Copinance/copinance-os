"""Unit tests for ask CLI command."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copinanceos.cli.ask import ask
from copinanceos.domain.models.job import JobScope, JobTimeframe
from copinanceos.domain.models.market import MarketType, OptionSide


@pytest.mark.unit
class TestAskCLI:
    @patch("copinanceos.cli.ask.ensure_profile_with_literacy")
    @patch("copinanceos.cli.ask.container.job_runner")
    @patch("copinanceos.cli.ask.console")
    def test_ask_market_wide_runs_workflow_without_persisting(
        self,
        mock_console: MagicMock,
        mock_job_runner: MagicMock,
        mock_ensure_profile: MagicMock,
    ) -> None:
        mock_ensure_profile.return_value = None
        mock_runner = AsyncMock()
        mock_runner.run = AsyncMock(
            return_value=MagicMock(success=True, results={"analysis": "hello"}, error_message=None)
        )
        mock_job_runner.return_value = mock_runner

        ask(
            question="What is market sentiment?",
            instrument=None,
            market_type=MarketType.EQUITY,
            expiration_date=None,
            option_side=OptionSide.ALL,
            market_index="SPY",
            timeframe=JobTimeframe.MID_TERM,
            profile_id=None,
        )

        job = mock_runner.run.call_args[0][0]
        context = mock_runner.run.call_args[0][1]
        assert job.scope == JobScope.MARKET
        assert job.market_index == "SPY"
        assert job.workflow_type == "agent"
        assert context["question"] == "What is market sentiment?"
        assert mock_console.print.called
