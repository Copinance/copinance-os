"""One-off analysis CLI commands."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import typer
from rich.console import Console

from copinanceos.cli.error_handler import handle_cli_error
from copinanceos.cli.profile_context import ensure_profile_with_literacy
from copinanceos.cli.utils import async_command, save_workflow_results
from copinanceos.domain.models.job import Job, JobScope, JobTimeframe
from copinanceos.domain.models.market import MarketType, OptionSide
from copinanceos.infrastructure.config import get_settings
from copinanceos.infrastructure.containers import container

analyze_app = typer.Typer(
    help="Run one-off analysis (results saved under the versioned results directory)"
)
market_analyze_app = typer.Typer(help="Analyze a market instrument")
analyze_app.add_typer(market_analyze_app, name="market")
console = Console()


def _print_workflow_response(response: Any) -> None:
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


@market_analyze_app.command("equity")
@async_command
async def analyze_equity(
    symbol: str = typer.Argument(..., help="Equity symbol"),
    timeframe: JobTimeframe = typer.Option(JobTimeframe.MID_TERM, help="Analysis timeframe"),
    profile_id: UUID | None = typer.Option(None, help="Profile ID for context (optional)"),
) -> None:
    """Run the static equity workflow."""
    final_profile_id = await ensure_profile_with_literacy(profile_id)
    job = Job(
        scope=JobScope.INSTRUMENT,
        market_type=MarketType.EQUITY,
        instrument_symbol=symbol,
        market_index=None,
        timeframe=timeframe,
        workflow_type=MarketType.EQUITY.value,
        profile_id=final_profile_id,
        error_message=None,
    )
    try:
        with console.status("[bold blue]Analyzing equity..."):
            runner = container.job_runner()
            response = await runner.run(job, {})
        _print_workflow_response(response)
    except Exception as e:
        handle_cli_error(e, context={"instrument_symbol": symbol, "workflow": "equity"})


@market_analyze_app.command("options")
@async_command
async def analyze_options(
    underlying_symbol: str = typer.Argument(..., help="Underlying symbol"),
    expiration_date: str | None = typer.Option(
        None,
        "--expiration",
        help="Optional expiration date in YYYY-MM-DD format",
    ),
    option_side: OptionSide = typer.Option(
        OptionSide.ALL,
        "--side",
        help="Options side to analyze",
    ),
    timeframe: JobTimeframe = typer.Option(JobTimeframe.SHORT_TERM, help="Analysis timeframe"),
    profile_id: UUID | None = typer.Option(None, help="Profile ID for context (optional)"),
) -> None:
    """Run the static options workflow."""
    final_profile_id = await ensure_profile_with_literacy(profile_id)
    job = Job(
        scope=JobScope.INSTRUMENT,
        market_type=MarketType.OPTIONS,
        instrument_symbol=underlying_symbol,
        market_index=None,
        timeframe=timeframe,
        workflow_type=MarketType.OPTIONS.value,
        profile_id=final_profile_id,
        error_message=None,
    )
    context = {"expiration_date": expiration_date, "option_side": option_side.value}
    try:
        with console.status("[bold blue]Analyzing options market..."):
            runner = container.job_runner()
            response = await runner.run(job, context)
        _print_workflow_response(response)
    except Exception as e:
        handle_cli_error(
            e,
            context={
                "instrument_symbol": underlying_symbol,
                "workflow": "options",
                "expiration_date": expiration_date,
            },
        )


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
    """Run the macro + market regime workflow."""
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

    job = Job(
        scope=JobScope.MARKET,
        market_type=None,
        instrument_symbol=None,
        market_index=market_index,
        timeframe=JobTimeframe.MID_TERM,
        workflow_type="macro",
        profile_id=None,
        error_message=None,
    )
    try:
        with console.status("[bold blue]Running macro analysis..."):
            runner = container.job_runner()
            response = await runner.run(job, context)
        _print_workflow_response(response)
    except Exception as e:
        handle_cli_error(e, context={"workflow": "macro", "market_index": market_index})
