"""One-off analysis CLI commands."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import typer
from rich.console import Console

from copinanceos.application.use_cases.workflow import RunWorkflowRequest
from copinanceos.cli.error_handler import handle_cli_error
from copinanceos.cli.profile_context import ensure_profile_with_literacy
from copinanceos.cli.utils import async_command, save_workflow_results
from copinanceos.domain.models.job import JobScope, JobTimeframe
from copinanceos.infrastructure.config import get_settings
from copinanceos.infrastructure.containers import container

analyze_app = typer.Typer(help="Run one-off analysis (results saved to .copinance/results/)")
console = Console()


@analyze_app.command("stock")
@async_command
async def analyze_stock(
    symbol: str = typer.Argument(..., help="Stock symbol"),
    timeframe: JobTimeframe = typer.Option(JobTimeframe.MID_TERM, help="Analysis timeframe"),
    profile_id: UUID | None = typer.Option(None, help="Profile ID for context (optional)"),
) -> None:
    """Run the static stock workflow. Results are saved to .copinance/results/."""
    final_profile_id = await ensure_profile_with_literacy(profile_id)

    use_case = container.run_workflow_use_case()
    try:
        with console.status("[bold blue]Analyzing stock..."):
            response = await use_case.execute(
                RunWorkflowRequest(
                    scope=JobScope.STOCK,
                    stock_symbol=symbol,
                    market_index=None,
                    timeframe=timeframe,
                    workflow_type="stock",
                    profile_id=final_profile_id,
                    context={},
                )
            )
        if response.success and response.results:
            console.print("\n✓ Completed", style="bold green")
            saved = save_workflow_results(response.results, get_settings().storage_path)
            if saved:
                console.print(f"Results saved to [cyan]{saved}[/cyan]")
            console.print("\n[bold]Results:[/bold]")
            for key, value in response.results.items():
                if key not in {"analysis", "tool_calls"}:
                    console.print(f"  {key}: {value}")
        elif not response.success:
            console.print("\n✗ Failed", style="bold red")
            console.print(f"Error: {response.error_message}")
        else:
            console.print("\n✓ Completed", style="bold green")
    except Exception as e:
        handle_cli_error(e, context={"symbol": symbol, "workflow": "stock"})


@analyze_app.command("macro")
@async_command
async def analyze_macro(
    market_index: str = typer.Option(
        "SPY",
        "--market-index",
        "-m",
        help="Market index symbol to analyze (e.g., SPY, QQQ, DIA, IWM). Default: SPY",
    ),
    lookback_days: int = typer.Option(
        252,
        "--lookback-days",
        "-d",
        help="Number of days to look back. Default: 252 (1 trading year)",
    ),
    include_vix: bool = typer.Option(
        True,
        "--include-vix/--no-include-vix",
        help="Include VIX analysis",
    ),
    include_market_breadth: bool = typer.Option(
        True,
        "--include-market-breadth/--no-include-market-breadth",
        help="Include market breadth indicators",
    ),
    include_sector_rotation: bool = typer.Option(
        True,
        "--include-sector-rotation/--no-include-sector-rotation",
        help="Include sector rotation analysis",
    ),
    include_rates: bool = typer.Option(
        True,
        "--include-rates/--no-include-rates",
        help="Include interest rates analysis (FRED-first, fallback to yfinance)",
    ),
    include_credit: bool = typer.Option(
        True,
        "--include-credit/--no-include-credit",
        help="Include credit spreads analysis (FRED-first, fallback to yfinance)",
    ),
    include_commodities: bool = typer.Option(
        True,
        "--include-commodities/--no-include-commodities",
        help="Include commodities/energy analysis (FRED-first, fallback to yfinance)",
    ),
    include_labor: bool = typer.Option(
        True,
        "--include-labor/--no-include-labor",
        help="Include labor market indicators",
    ),
    include_housing: bool = typer.Option(
        True,
        "--include-housing/--no-include-housing",
        help="Include housing indicators",
    ),
    include_manufacturing: bool = typer.Option(
        True,
        "--include-manufacturing/--no-include-manufacturing",
        help="Include manufacturing indicators",
    ),
    include_consumer: bool = typer.Option(
        True,
        "--include-consumer/--no-include-consumer",
        help="Include consumer spending/confidence indicators",
    ),
    include_global: bool = typer.Option(
        True,
        "--include-global/--no-include-global",
        help="Include global indicators",
    ),
    include_advanced: bool = typer.Option(
        True,
        "--include-advanced/--no-include-advanced",
        help="Include advanced indicators",
    ),
) -> None:
    """Run the macro + market regime workflow. Results are saved to .copinance/results/."""
    context: dict[str, Any] = {
        "market_index": market_index.upper(),
        "lookback_days": lookback_days,
        "include_vix": include_vix,
        "include_market_breadth": include_market_breadth,
        "include_sector_rotation": include_sector_rotation,
        "include_rates": include_rates,
        "include_credit": include_credit,
        "include_commodities": include_commodities,
        "include_labor": include_labor,
        "include_housing": include_housing,
        "include_manufacturing": include_manufacturing,
        "include_consumer": include_consumer,
        "include_global": include_global,
        "include_advanced": include_advanced,
    }

    use_case = container.run_workflow_use_case()
    try:
        with console.status("[bold blue]Running macro analysis..."):
            response = await use_case.execute(
                RunWorkflowRequest(
                    scope=JobScope.MARKET,
                    stock_symbol=None,
                    market_index=market_index,
                    timeframe=JobTimeframe.MID_TERM,
                    workflow_type="macro",
                    profile_id=None,
                    context=context,
                )
            )
        if response.success and response.results:
            console.print("\n✓ Completed", style="bold green")
            saved = save_workflow_results(response.results, get_settings().storage_path)
            if saved:
                console.print(f"Results saved to [cyan]{saved}[/cyan]")
            console.print("\n[bold]Results:[/bold]")
            for key, value in response.results.items():
                console.print(f"  {key}: {value}")
        elif not response.success:
            console.print("\n✗ Failed", style="bold red")
            console.print(f"Error: {response.error_message}")
        else:
            console.print("\n✓ Completed", style="bold green")
    except Exception as e:
        handle_cli_error(e, context={"workflow": "macro", "market_index": market_index})
