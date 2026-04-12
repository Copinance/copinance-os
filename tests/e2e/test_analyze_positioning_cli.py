"""E2E: analyze positioning CLI (mocked use case, no network)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer.testing

from copinance_os.domain.models.job import RunJobResult
from copinance_os.interfaces.cli.commands.analyze import analyze_app


@pytest.mark.e2e
@patch("copinance_os.interfaces.cli.commands.analyze.ensure_profile_with_literacy")
@patch("copinance_os.interfaces.cli.commands.analyze.get_container")
def test_analyze_positioning_json_stdout(
    mock_get_container: MagicMock,
    mock_ensure_profile: MagicMock,
) -> None:
    mock_ensure_profile.return_value = None
    mock_uc = MagicMock()
    mock_uc.execute = AsyncMock(
        return_value=RunJobResult(
            success=True,
            results={
                "positioning": {"symbol": "SPY", "market_bias": "neutral", "window": "near"},
            },
            error_message=None,
        )
    )
    mock_get_container.return_value.analyze_instrument_use_case.return_value = mock_uc

    runner = typer.testing.CliRunner()
    result = runner.invoke(
        analyze_app,
        ["--json", "positioning", "SPY", "-w", "near"],
    )
    assert result.exit_code == 0
    assert '"success": true' in result.stdout
    mock_uc.execute.assert_called_once()
    req = mock_uc.execute.call_args[0][0]
    assert req.symbol == "SPY"
    assert req.positioning_window == "near"
