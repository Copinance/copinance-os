"""Unit tests for main CLI commands."""

import pytest
import typer.testing

import copinance_os.interfaces.cli.__main__  # noqa: PLC0415 - Testing module import behavior
from copinance_os.interfaces.cli import (
    _root_cli_epilog_natural_language,
    app,
    main,
    version_app,
)


@pytest.mark.unit
class TestMainCLI:
    """Test main CLI commands."""

    def test_version_command(self) -> None:
        """Test version command."""
        runner = typer.testing.CliRunner()
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "Copinance OS" in result.stdout

    def test_main_module_entry_point(self) -> None:
        """Test that __main__.py exposes main()."""
        assert hasattr(copinance_os.interfaces.cli.__main__, "main")
        assert copinance_os.interfaces.cli.__main__.main is main

    def test_cli_app_structure(self) -> None:
        """Test that CLI app has correct structure."""
        assert app is not None
        assert hasattr(app, "registered_commands") or hasattr(app, "commands")

    def test_root_help_epilog_natural_language_table(self) -> None:
        """Root epilog uses paragraph breaks so Typer/Rich prints aligned example rows."""
        epilog = _root_cli_epilog_natural_language()
        assert "Natural Language Examples" in epilog
        assert "Question only" in epilog
        assert 'copinance "How is Tesla doing financially?"' in epilog
        assert "copinance --json" in epilog
        assert "\n\n" in epilog


@pytest.mark.unit
class TestCLIIntegration:
    """Test CLI integration and command registration (lazy subcommands: analyze, cache, market, profile)."""

    def test_subcommands_registered(self) -> None:
        """Test that lazy subcommands (analyze, cache, market, profile) are registered."""
        names = [c.name for c in app.registered_commands]
        for name in ("analyze", "cache", "market", "profile"):
            assert name in names, f"Expected subcommand {name!r} in {names}"

    def test_version_app_available(self) -> None:
        """Test that version subcommand is available (non-lazy)."""
        assert version_app is not None
        assert app is not None
