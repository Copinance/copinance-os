"""Console entry: dispatch generic research vs Typer subcommands."""

from __future__ import annotations

import sys

from copinance_os.interfaces.cli.dispatch import GenericInvocation, TyperInvocation, parse_root_argv


def main() -> None:
    """Console entry: dispatch generic research vs Typer subcommands."""
    # Local imports: avoid loading DI/workflows/asyncio/Typer until the chosen path needs them
    # (``copinance help`` must not pull the full research stack or asyncio).
    from dotenv import load_dotenv

    load_dotenv()

    argv = sys.argv[1:]
    parsed = parse_root_argv(argv)
    if isinstance(parsed, GenericInvocation):
        import asyncio

        from copinance_os.interfaces.cli.commands.generic_research import run_generic_research

        asyncio.run(
            run_generic_research(
                parsed.question,
                json_output=parsed.json_output,
                include_prompt_in_results=parsed.include_prompt_in_results,
                stream=parsed.stream,
            )
        )
        return
    from copinance_os.interfaces.cli.root import app

    assert isinstance(parsed, TyperInvocation)
    old_argv = sys.argv
    sys.argv = [old_argv[0]] + parsed.argv
    try:
        app()
    finally:
        sys.argv = old_argv
