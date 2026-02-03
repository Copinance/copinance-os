"""Unit tests for ask CLI command."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copinanceos.cli.ask import ask
from copinanceos.domain.models.job import JobScope, JobTimeframe


@pytest.mark.unit
class TestAskCLI:
    @patch("copinanceos.cli.ask.ensure_profile_with_literacy")
    @patch("copinanceos.cli.ask.container.run_workflow_use_case")
    @patch("copinanceos.cli.ask.console")
    def test_ask_market_wide_runs_workflow_without_persisting(
        self,
        mock_console: MagicMock,
        mock_run_provider: MagicMock,
        mock_ensure_profile: MagicMock,
    ) -> None:
        mock_ensure_profile.return_value = None
        mock_uc = AsyncMock()
        mock_uc.execute = AsyncMock(
            return_value=MagicMock(success=True, results={"analysis": "hello"}, error_message=None)
        )
        mock_run_provider.return_value = mock_uc

        ask(
            question="What is market sentiment?",
            symbol=None,
            market_index="SPY",
            timeframe=JobTimeframe.MID_TERM,
            profile_id=None,
        )

        req = mock_uc.execute.call_args[0][0]
        assert req.scope == JobScope.MARKET.value
        assert req.market_index == "SPY"
        assert req.workflow_type == "agent"
        assert req.context["question"] == "What is market sentiment?"
        assert mock_console.print.called
