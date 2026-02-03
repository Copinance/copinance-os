"""Conversational Q&A CLI commands."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from copinanceos.application.use_cases.workflow import RunWorkflowRequest
from copinanceos.cli.profile_context import ensure_profile_with_literacy
from copinanceos.cli.utils import async_command, save_workflow_results
from copinanceos.domain.models.job import JobScope, JobTimeframe
from copinanceos.infrastructure.config import get_settings
from copinanceos.infrastructure.containers import container

ask_app = typer.Typer(help="Ask questions (agentic, requires LLM configuration)")
console = Console()


def _display_agentic_results(results: dict[str, Any]) -> None:
    if "analysis" in results and results["analysis"]:
        analysis_text = str(results["analysis"])
        console.print("\n[bold]Answer:[/bold]")
        try:
            console.print(Panel(Markdown(analysis_text), border_style="blue"))
        except Exception:
            console.print(Panel(analysis_text, border_style="blue"))
        return

    console.print("\n[bold yellow]No answer available[/bold yellow]")
    console.print("Results:", results)


@ask_app.callback(invoke_without_command=True)
@async_command
async def ask(
    question: str = typer.Argument(..., help="Question to ask (about a stock or the market)"),
    symbol: str | None = typer.Option(
        None, "--symbol", "-s", help="Stock symbol (omit for market-wide questions)"
    ),
    market_index: str = typer.Option(
        "SPY",
        "--market-index",
        "-m",
        help="Anchor market index for market-wide questions. Default: SPY",
    ),
    timeframe: JobTimeframe = typer.Option(JobTimeframe.MID_TERM, help="Timeframe context"),
    profile_id: UUID | None = typer.Option(None, help="Profile ID for context (optional)"),
) -> None:
    """Ask a question using the agent workflow. Results are saved to .copinance/results/."""
    final_profile_id = await ensure_profile_with_literacy(profile_id)

    is_market_wide = symbol is None
    scope = JobScope.MARKET if is_market_wide else JobScope.STOCK

    if is_market_wide:
        console.print(f"[bold]Market-wide question:[/bold] {question}\n")
    else:
        console.print(f"[bold]Question about {symbol}:[/bold] {question}\n")

    use_case = container.run_workflow_use_case()
    response = await use_case.execute(
        RunWorkflowRequest(
            scope=scope,
            stock_symbol=symbol.upper() if symbol else None,
            market_index=market_index.upper() if is_market_wide else None,
            timeframe=timeframe,
            workflow_type="agent",
            profile_id=final_profile_id,
            context={"question": question},
        )
    )

    if response.success and response.results:
        saved = save_workflow_results(response.results, get_settings().storage_path)
        if saved:
            console.print(f"Results saved to [cyan]{saved}[/cyan]")
        _display_agentic_results(response.results)
    elif not response.success:
        console.print("\n✗ Failed to get answer", style="bold red")
        console.print(f"Error: {response.error_message}")
    else:
        console.print("\n[bold yellow]No answer available[/bold yellow]")
