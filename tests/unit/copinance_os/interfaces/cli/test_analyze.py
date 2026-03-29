"""Unit tests for progressive analyze CLI commands."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copinance_os.domain.models.job import JobTimeframe, RunJobResult
from copinance_os.domain.models.market import OptionSide
from copinance_os.interfaces.cli.commands.analyze import (
    analyze_equity,
    analyze_macro,
    analyze_options,
)
from copinance_os.research.workflows.analyze import (
    AnalyzeInstrumentRequest,
    AnalyzeMarketRequest,
    AnalyzeMode,
)


def _typer_ctx() -> MagicMock:
    ctx = MagicMock()
    ctx.obj = {}
    return ctx


@pytest.mark.unit
class TestAnalyzeCLI:
    @patch("copinance_os.interfaces.cli.commands.analyze.ensure_profile_with_literacy")
    @patch("copinance_os.interfaces.cli.shared.run_job_output.get_storage_path_safe")
    @patch("copinance_os.interfaces.cli.commands.analyze.get_container")
    @patch("copinance_os.interfaces.cli.shared.run_job_output.console")
    def test_analyze_equity_calls_use_case_and_displays(
        self,
        mock_console: MagicMock,
        mock_get_container: MagicMock,
        mock_get_storage_path_safe: MagicMock,
        mock_ensure_profile: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_ensure_profile.return_value = None
        mock_get_storage_path_safe.return_value = str(tmp_path)
        mock_uc = MagicMock()
        mock_uc.execute = AsyncMock(
            return_value=RunJobResult(success=True, results={"summary": "ok"}, error_message=None)
        )
        mock_get_container.return_value.analyze_instrument_use_case.return_value = mock_uc

        analyze_equity(
            _typer_ctx(),
            symbol="AAPL",
            timeframe=JobTimeframe.MID_TERM,
            question=None,
            mode=AnalyzeMode.AUTO,
            profile_id=None,
            include_prompt_in_results=False,
        )

        mock_uc.execute.assert_called_once()
        request = mock_uc.execute.call_args[0][0]
        assert isinstance(request, AnalyzeInstrumentRequest)
        assert request.symbol == "AAPL"
        assert request.timeframe == JobTimeframe.MID_TERM
        assert request.question is None
        assert mock_console.print.called
        assert (tmp_path / "results" / "v2").exists()

    @patch("copinance_os.interfaces.cli.commands.analyze.ensure_profile_with_literacy")
    @patch("copinance_os.interfaces.cli.commands.analyze.get_container")
    @patch("copinance_os.interfaces.cli.shared.run_job_output.console")
    def test_analyze_options_agentic_calls_use_case(
        self,
        mock_console: MagicMock,
        mock_get_container: MagicMock,
        mock_ensure_profile: MagicMock,
    ) -> None:
        mock_ensure_profile.return_value = None
        mock_uc = MagicMock()
        mock_uc.execute = AsyncMock(
            return_value=RunJobResult(
                success=True,
                results={"analysis": "Bearish skew", "tool_calls": []},
                error_message=None,
            )
        )
        mock_get_container.return_value.analyze_instrument_use_case.return_value = mock_uc

        analyze_options(
            _typer_ctx(),
            underlying_symbol="AAPL",
            expiration_date="2026-06-19",
            option_side=OptionSide.CALL,
            timeframe=JobTimeframe.SHORT_TERM,
            question="Is skew bearish?",
            mode=AnalyzeMode.AUTO,
            profile_id=None,
            include_prompt_in_results=False,
        )

        request = mock_uc.execute.call_args[0][0]
        assert isinstance(request, AnalyzeInstrumentRequest)
        assert request.symbol == "AAPL"
        assert request.question == "Is skew bearish?"
        assert request.expiration_date == "2026-06-19"
        assert request.option_side == OptionSide.CALL
        assert mock_console.print.called

    @patch("copinance_os.interfaces.cli.commands.analyze.ensure_profile_with_literacy")
    @patch("copinance_os.interfaces.cli.shared.run_job_output.get_storage_path_safe")
    @patch("copinance_os.interfaces.cli.commands.analyze.get_container")
    @patch("copinance_os.interfaces.cli.shared.run_job_output.console")
    def test_analyze_macro_calls_use_case_and_displays(
        self,
        mock_console: MagicMock,
        mock_get_container: MagicMock,
        mock_get_storage_path_safe: MagicMock,
        mock_ensure_profile: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_ensure_profile.return_value = None
        mock_get_storage_path_safe.return_value = str(tmp_path)
        mock_uc = MagicMock()
        mock_uc.execute = AsyncMock(
            return_value=RunJobResult(
                success=True,
                results={"macro": {"available": True}},
                error_message=None,
            )
        )
        mock_get_container.return_value.analyze_market_use_case.return_value = mock_uc

        analyze_macro(
            _typer_ctx(),
            market_index="SPY",
            timeframe=JobTimeframe.MID_TERM,
            question=None,
            mode=AnalyzeMode.AUTO,
            lookback_days=90,
            include_vix=True,
            include_market_breadth=True,
            include_sector_rotation=True,
            include_rates=True,
            include_credit=True,
            include_commodities=True,
            include_labor=True,
            include_housing=True,
            include_manufacturing=True,
            include_consumer=True,
            include_global=True,
            include_advanced=True,
            profile_id=None,
            include_prompt_in_results=False,
        )

        mock_uc.execute.assert_called_once()
        request = mock_uc.execute.call_args[0][0]
        assert isinstance(request, AnalyzeMarketRequest)
        assert request.market_index == "SPY"
        assert request.lookback_days == 90
        assert mock_console.print.called
        assert (tmp_path / "results" / "v2").exists()
