"""Command-line interface for Copinance OS."""

import importlib
import sys

from dotenv import load_dotenv

# Load .env into os.environ so LLM/config env vars are visible to config_loader and Settings
load_dotenv()

import typer
from rich.console import Console

from copinance_os import __version__

app = typer.Typer(
    name="copinance",
    help="Copinance OS - Open-source market analysis platform",
    no_args_is_help=True,
)

# Context settings so lazy commands can receive all remaining argv and delegate.
_LAZY_CONTEXT = {"allow_extra_args": True, "ignore_unknown_options": True}


def _lazy_command(
    name: str,
    help_text: str,
    module_path: str,
    attr: str,
) -> None:
    """Register a lazy-loaded subcommand: imports and runs the real app on first use."""

    @app.command(
        name,
        help=help_text,
        context_settings=_LAZY_CONTEXT,
        add_help_option=False,  # So --help is passed through to the real sub-app; callback always runs
    )
    def _delegate(ctx: typer.Context) -> None:
        # Get remainder: after "copinance" and this command (e.g. analyze) -> equity, --help.
        # Click sets ctx.args when allow_extra_args=True; fallback to sys.argv[2:] if empty.
        old_argv = list(sys.argv)
        remainder = list(getattr(ctx, "args", []) or [])
        if not remainder and len(old_argv) > 2:
            remainder = old_argv[2:]
        new_argv = [f"{old_argv[0]} {name}"] + remainder
        sys.argv = new_argv
        try:
            mod = importlib.import_module(module_path)
            real_app = getattr(mod, attr)
            real_app()
        finally:
            sys.argv = old_argv

    return None


version_app = typer.Typer(help="Show version information.", invoke_without_command=True)


@version_app.callback()
def _version_callback() -> None:
    console = Console()
    console.print(f"Copinance OS v{__version__}", style="bold green")


# Lazy subcommands: analyze, cache, market, profile load only when invoked.
_lazy_command(
    "analyze",
    "Run progressive analysis. Without a question it runs deterministic analysis; with a question it runs tool-using question-driven analysis.",
    "copinance_os.interfaces.cli.analyze",
    "analyze_app",
)
_lazy_command(
    "cache", "Cache management commands", "copinance_os.interfaces.cli.cache", "cache_app"
)
_lazy_command(
    "market",
    "Market data: search, quote, history, options (BSM Greeks via QuantLib), fundamentals",
    "copinance_os.interfaces.cli.market",
    "market_app",
)
_lazy_command(
    "profile",
    "Analysis profile management commands",
    "copinance_os.interfaces.cli.profile",
    "profile_app",
)
app.add_typer(version_app, name="version")


if __name__ == "__main__":
    app()
