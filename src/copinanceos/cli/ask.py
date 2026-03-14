"""Conversational Q&A CLI commands."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from copinanceos.cli.profile_context import ensure_profile_with_literacy
from copinanceos.cli.utils import async_command, save_workflow_results
from copinanceos.domain.models.job import Job, JobScope, JobTimeframe
from copinanceos.domain.models.market import MarketType, OptionSide
from copinanceos.infrastructure.config import get_settings
from copinanceos.infrastructure.containers import container

ask_app = typer.Typer(help="Ask questions (agentic, requires LLM configuration)")
console = Console()


def _display_agentic_results(results: dict[str, Any], show_prompt: bool = False) -> None:
    if "analysis" in results and results["analysis"]:
        if show_prompt and ("system_prompt" in results or "user_prompt" in results):
            console.print("\n[bold]Prompt used:[/bold]")
            if results.get("system_prompt"):
                console.print("[dim]System:[/dim]")
                try:
                    console.print(Panel(results["system_prompt"], border_style="dim"))
                except Exception:
                    console.print(results["system_prompt"])
            if results.get("user_prompt"):
                console.print("[dim]User:[/dim]")
                try:
                    console.print(Panel(results["user_prompt"], border_style="dim"))
                except Exception:
                    console.print(results["user_prompt"])
            console.print()
        analysis_text = str(results["analysis"])
        console.print("\n[bold]Answer:[/bold]")
        try:
            console.print(Panel(Markdown(analysis_text), border_style="blue"))
        except Exception:
            console.print(Panel(analysis_text, border_style="blue"))
        return

    # Workflow ran but returned no analysis (e.g. LLM not configured, provider missing)
    if results.get("status") == "failed" and results.get("error"):
        console.print("\n[bold yellow]Agent could not run[/bold yellow]")
        console.print(f"[yellow]{results['error']}[/yellow]")
        if results.get("message"):
            console.print(f"[dim]{results['message']}[/dim]")
        # Show config hint for LLM-related failures
        err = (results.get("error") or "").lower()
        if "llm" in err or "provider" in err:
            console.print("\n[bold]How to configure:[/bold]")
            console.print(
                "  • CLI: add to .env (copy from .env.example). Example for Gemini:\n"
                "    [cyan]COPINANCEOS_LLM_PROVIDER=gemini[/cyan]\n"
                "    [cyan]COPINANCEOS_GEMINI_API_KEY=your-api-key[/cyan]"
            )
            console.print("  • Docs: docs/pages/user-guide/configuration.mdx")
        return

    console.print("\n[bold yellow]No answer available[/bold yellow]")
    if results:
        console.print("Results:", results)


@ask_app.callback(invoke_without_command=True)
@async_command
async def ask(
    question: str = typer.Option(
        ...,
        "--question",
        "-q",
        help="Question to ask (about an instrument or the market). Quote long text.",
    ),
    instrument: str | None = typer.Option(
        None,
        "--instrument",
        "-i",
        help="Instrument symbol (omit for market-wide questions)",
    ),
    market_type: MarketType = typer.Option(
        MarketType.EQUITY,
        "--market-type",
        help="Instrument market segment for instrument-specific questions",
    ),
    expiration_date: str | None = typer.Option(
        None,
        "--expiration",
        help="Optional options expiration date in YYYY-MM-DD format",
    ),
    option_side: OptionSide = typer.Option(
        OptionSide.ALL,
        "--side",
        help="Optional options side hint (call, put, all)",
    ),
    market_index: str = typer.Option(
        "SPY",
        "--market-index",
        "-m",
        help="Anchor market index for market-wide questions",
    ),
    timeframe: JobTimeframe = typer.Option(JobTimeframe.MID_TERM, help="Timeframe context"),
    profile_id: UUID | None = typer.Option(None, help="Profile ID for context"),
    show_prompt: bool = typer.Option(
        False,
        "--show-prompt",
        help="Also display the prompt used for the question (system and user parts).",
    ),
) -> None:
    """Ask a question using the agent workflow (requires LLM configuration)."""
    final_profile_id = await ensure_profile_with_literacy(profile_id)

    is_market_wide = instrument is None
    scope = JobScope.MARKET if is_market_wide else JobScope.INSTRUMENT

    if is_market_wide:
        console.print(f"[bold]Market-wide question:[/bold] {question}\n")
    else:
        console.print(f"[bold]Question about {instrument}:[/bold] {question}\n")

    job = Job(
        scope=scope,
        market_type=None if is_market_wide else market_type,
        instrument_symbol=instrument.upper() if instrument else None,
        market_index=market_index.upper() if is_market_wide else None,
        timeframe=timeframe,
        workflow_type="agent",
        profile_id=final_profile_id,
        error_message=None,
    )
    context = {
        "question": question,
        "market_type": market_type.value,
        "expiration_date": expiration_date,
        "option_side": option_side.value,
        "include_prompt": show_prompt,
    }
    runner = container.job_runner()
    response = await runner.run(job, context)

    if response.success and response.results:
        saved = save_workflow_results(response.results, get_settings().storage_path)
        if saved:
            console.print(f"Results saved to [cyan]{saved}[/cyan]")
        _display_agentic_results(response.results, show_prompt=show_prompt)
    elif not response.success:
        console.print("\n✗ Failed to get answer", style="bold red")
        console.print(f"Error: {response.error_message or 'Unknown error'}")
    else:
        console.print("\n[bold yellow]No answer available[/bold yellow]")
