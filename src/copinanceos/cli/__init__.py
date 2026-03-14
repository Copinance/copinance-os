"""Command-line interface for Copinance OS."""

from dotenv import load_dotenv

# Load .env into os.environ so LLM/config env vars are visible to config_loader and Settings
load_dotenv()

import typer
from rich.console import Console

from copinanceos import __version__
from copinanceos.cli.analyze import analyze_app
from copinanceos.cli.ask import ask_app
from copinanceos.cli.cache import cache_app
from copinanceos.cli.market import market_app
from copinanceos.cli.profile import profile_app

app = typer.Typer(
    name="copinance",
    help="Copinance OS - Open-source market research platform",
    no_args_is_help=True,
)

# Register sub-commands (all use .copinance for cache/storage)
app.add_typer(market_app, name="market")
app.add_typer(profile_app, name="profile")
app.add_typer(analyze_app, name="analyze")
app.add_typer(ask_app, name="ask")
app.add_typer(cache_app, name="cache")


@app.command()
def version() -> None:
    """Show version information."""
    console = Console()
    console.print(f"Copinance OS v{__version__}", style="bold green")


if __name__ == "__main__":
    app()
