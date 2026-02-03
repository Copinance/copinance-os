"""Unit tests for analyze CLI commands."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copinanceos.cli.analyze import analyze_macro, analyze_stock
from copinanceos.domain.models.job import JobScope, JobTimeframe


@pytest.mark.unit
class TestAnalyzeCLI:
    @patch("copinanceos.cli.analyze.ensure_profile_with_literacy")
    @patch("copinanceos.cli.analyze.container.run_workflow_use_case")
    @patch("copinanceos.cli.analyze.console")
    def test_analyze_stock_runs_workflow_without_persisting(
        self,
        mock_console: MagicMock,
        mock_run_provider: MagicMock,
        mock_ensure_profile: MagicMock,
    ) -> None:
        mock_ensure_profile.return_value = None
        mock_uc = AsyncMock()
        mock_uc.execute = AsyncMock(
            return_value=MagicMock(success=True, results={"summary": "ok"}, error_message=None)
        )
        mock_run_provider.return_value = mock_uc

        analyze_stock(symbol="AAPL", timeframe=JobTimeframe.MID_TERM, profile_id=None)

        req = mock_uc.execute.call_args[0][0]
        assert req.scope == JobScope.STOCK.value
        assert req.stock_symbol == "AAPL"
        assert req.workflow_type == "stock"
        assert mock_console.print.called

    @patch("copinanceos.cli.analyze.container.run_workflow_use_case")
    @patch("copinanceos.cli.analyze.console")
    def test_analyze_macro_runs_workflow_without_persisting(
        self,
        mock_console: MagicMock,
        mock_run_provider: MagicMock,
    ) -> None:
        mock_uc = AsyncMock()
        mock_uc.execute = AsyncMock(
            return_value=MagicMock(
                success=True, results={"macro": {"available": True}}, error_message=None
            )
        )
        mock_run_provider.return_value = mock_uc

        analyze_macro(market_index="SPY", lookback_days=90)

        req = mock_uc.execute.call_args[0][0]
        assert req.scope == JobScope.MARKET.value
        assert req.market_index == "SPY"
        assert req.workflow_type == "macro"
        assert req.context["market_index"] == "SPY"
        assert req.context["lookback_days"] == 90
        assert mock_console.print.called
