"""Root Typer application: lazy subcommands and help epilog."""

import importlib
import sys

import typer
from rich.console import Console

from copinance_os import __version__


def _rich_help_section_box(title: str, lines: list[str]) -> str:
    """Bordered block using the same light box-drawing style as Typer/Rich help tables.

    Typer's Rich help flattens single ``\\n`` within an epilog paragraph (joins with spaces).
    Each box line is therefore emitted as its *own* paragraph (``\\n\\n`` between lines) so
    the layout is preserved; paragraphs are rejoined with ``\\n`` for display.
    """
    if not lines:
        return ""
    content_w = max(len(line) for line in lines)
    padded = [line.ljust(content_w) for line in lines]
    inner_w = content_w + 2  # interior between ╭/╰ corners

    prefix = f"╭─ {title} "
    dash_fill = max(1, inner_w + 2 - len(prefix) - 1)
    top = prefix + "─" * dash_fill + "╮"
    body_lines = [f"│ {row} │" for row in padded]
    bottom = "╰" + "─" * inner_w + "╯"
    return "\n\n".join([top, *body_lines, bottom])


def _root_cli_epilog_natural_language() -> str:
    """Epilog for root ``--help``: natural-language examples in a bordered block (like Commands)."""
    rows: list[tuple[str, str]] = [
        ("Question only", 'copinance "How is Tesla doing financially?"'),
        ("Stream LLM tokens", 'copinance --stream "What is the VIX level?"'),
        ("JSON (stdout)", 'copinance --json "What is the VIX?"'),
        (
            "Include prompts",
            'copinance --include-prompt "Compare credit spreads to last year"',
        ),
        (
            "JSON + prompts",
            'copinance --json --include-prompt "Summarize labor and inflation"',
        ),
    ]
    col1_w = max(len(a) for a, _ in rows)

    def _row(a: str, b: str) -> str:
        return f"  {a:<{col1_w}}  {b}"

    table_lines = [_row(a, b) for a, b in rows]
    return _rich_help_section_box("Natural Language Examples", table_lines)


app = typer.Typer(
    name="copinance",
    help=(
        "Copinance OS: open-source market analysis (Python library + Typer/Rich CLI). "
        "Natural-language questions accept --json, --stream, and --include-prompt before the question."
    ),
    epilog=_root_cli_epilog_natural_language(),
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


_lazy_command(
    "analyze",
    "Run progressive analysis. Without a question it runs deterministic analysis; with a question it runs tool-using question-driven analysis. "
    "Group options: --json (machine output), --stream (token stream during question-driven). Use: copinance analyze --help.",
    "copinance_os.interfaces.cli.commands.analyze",
    "analyze_app",
)
_lazy_command(
    "cache", "Cache management commands", "copinance_os.interfaces.cli.commands.cache", "cache_app"
)
_lazy_command(
    "market",
    "Market data: search, quote, history, options (BSM Greeks via QuantLib), fundamentals",
    "copinance_os.interfaces.cli.commands.market",
    "market_app",
)
_lazy_command(
    "profile",
    "Analysis profile management commands",
    "copinance_os.interfaces.cli.commands.profile",
    "profile_app",
)
app.add_typer(version_app, name="version")
