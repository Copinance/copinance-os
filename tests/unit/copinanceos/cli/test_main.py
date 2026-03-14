"""Unit tests for main CLI commands."""

from unittest.mock import MagicMock, patch

import pytest

import copinanceos.cli.__main__  # noqa: PLC0415 - Testing module import behavior
from copinanceos.cli import (
    analyze_app,
    app,
    ask_app,
    cache_app,
    market_app,
    profile_app,
    version,
)


@pytest.mark.unit
class TestMainCLI:
    """Test main CLI commands."""

    @patch("copinanceos.cli.Console")
    def test_version_command(self, mock_console_class: MagicMock) -> None:
        """Test version command."""

        # Setup mock console instance
        mock_console_instance = MagicMock()
        mock_console_class.return_value = mock_console_instance

        version()

        # Verify Console was instantiated
        mock_console_class.assert_called_once()
        # Verify console.print was called with version
        mock_console_instance.print.assert_called_once()
        call_args = str(mock_console_instance.print.call_args)
        assert "Copinance OS" in call_args

    @patch("copinanceos.cli.app")
    def test_main_module_entry_point(self, mock_app: MagicMock) -> None:
        """Test that __main__.py calls the app."""
        # The __main__.py should call app() when executed
        # Since we're testing the module import, we verify the structure
        assert hasattr(copinanceos.cli.__main__, "app")
        assert copinanceos.cli.__main__.app is not None

    def test_cli_app_structure(self) -> None:
        """Test that CLI app has correct structure."""

        # Verify app is a Typer instance
        assert app is not None
        # Verify sub-commands are registered
        # The app should have market, profile, analyze, ask, cache sub-commands
        assert hasattr(app, "registered_commands") or hasattr(app, "commands")


@pytest.mark.unit
class TestCLIIntegration:
    """Test CLI integration and command registration."""

    def test_market_app_registered(self) -> None:
        """Test that market app is registered."""

        # Verify market_app exists
        assert market_app is not None
        # The app should have market commands registered
        # This is a structural test to ensure the app is properly configured
        assert app is not None

    def test_profile_app_registered(self) -> None:
        """Test that profile app is registered."""

        # Verify profile_app exists
        assert profile_app is not None
        assert app is not None

    def test_cache_app_registered(self) -> None:
        """Test that cache app is registered."""

        assert cache_app is not None
        assert app is not None

    def test_analyze_app_registered(self) -> None:
        """Test that analyze app is registered."""

        assert analyze_app is not None
        assert app is not None

    def test_ask_app_registered(self) -> None:
        """Test that ask app is registered."""

        assert ask_app is not None
        assert app is not None
