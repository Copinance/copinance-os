"""Analyze CLI: progressive instrument and market analysis."""

from __future__ import annotations

from uuid import UUID

import typer
from rich.console import Console

from copinance_os.domain.models.analysis import (
    AnalyzeInstrumentRequest,
    AnalyzeMarketRequest,
    AnalyzeMode,
)
from copinance_os.domain.models.job import JobTimeframe
from copinance_os.domain.models.market import MarketType, OptionSide
from copinance_os.interfaces.cli.shared.container_access import get_container
from copinance_os.interfaces.cli.shared.error_handler import handle_cli_error
from copinance_os.interfaces.cli.shared.profile_context import ensure_profile_with_literacy
from copinance_os.interfaces.cli.shared.run_job_output import render_run_job_results
from copinance_os.interfaces.cli.shared.utils import async_command
from copinance_os.research.workflows.analyze import AnalyzeInstrumentUseCase, AnalyzeMarketUseCase

analyze_app = typer.Typer(
    help=(
        "Run progressive analysis. Without a question it runs deterministic analysis; "
        "with a question it runs tool-using question-driven analysis. "
        "Use --stream (with subcommands) to print LLM tokens during question-driven runs; "
        "--json disables streaming and prints RunJobResult as JSON."
    ),
    invoke_without_command=False,
    no_args_is_help=True,
)


@analyze_app.callback()
def _analyze_group(
    ctx: typer.Context,
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print RunJobResult as JSON (success, results, error_message, report, report_exclusion_reason).",
    ),
    stream: bool = typer.Option(
        False,
        "--stream",
        help=(
            "Print LLM response tokens to stdout during question-driven runs (before run metadata). "
            "No effect for deterministic-only runs. Ignored when --json is set."
        ),
    ),
) -> None:
    ctx.obj = {"json_output": json_output, "stream": stream}


@analyze_app.command("equity")
@async_command
async def analyze_equity(
    ctx: typer.Context,
    symbol: str = typer.Argument(..., help="Equity symbol"),
    timeframe: JobTimeframe | None = typer.Option(
        None,
        help="Analysis timeframe. Defaults to mid_term.",
    ),
    question: str | None = typer.Option(
        None,
        "--question",
        "-q",
        help="Optional question. Providing a question triggers question-driven analysis in auto mode.",
    ),
    mode: AnalyzeMode = typer.Option(
        AnalyzeMode.AUTO,
        "--mode",
        help="Execution mode: auto, deterministic, or question_driven",
    ),
    profile_id: UUID | None = typer.Option(None, help="Profile ID for context (optional)"),
    include_prompt_in_results: bool = typer.Option(
        False,
        "--include-prompt",
        help="Include rendered prompts in the saved results for question-driven runs",
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Bypass data/tool cache reads and writes for this run",
    ),
) -> None:
    """Analyze an equity with deterministic or question-driven execution."""
    console = Console()
    final_profile_id = await ensure_profile_with_literacy(profile_id)
    use_case: AnalyzeInstrumentUseCase = get_container().analyze_instrument_use_case()
    json_output = bool(ctx.obj and ctx.obj.get("json_output"))
    stream_flag = bool(ctx.obj and ctx.obj.get("stream")) and not json_output
    request = AnalyzeInstrumentRequest(
        symbol=symbol,
        market_type=MarketType.EQUITY,
        timeframe=timeframe,
        question=question,
        mode=mode,
        expiration_date=None,
        expiration_dates=None,
        option_side=OptionSide.ALL,
        profile_id=final_profile_id,
        include_prompt_in_results=include_prompt_in_results,
        stream=stream_flag,
        run_id=None,
        no_cache=no_cache,
    )
    try:
        status_text = (
            "[bold blue]Analyzing equity with tools...[/bold blue]"
            if request.question
            else "[bold blue]Analyzing equity...[/bold blue]"
        )
        if stream_flag and request.question:
            console.print("[dim]Streaming (question-driven)…[/dim]\n")
            response = await use_case.execute(request)
            console.print()
        else:
            with console.status(status_text):
                response = await use_case.execute(request)
        render_run_job_results(response, json_output=json_output)
    except Exception as e:
        handle_cli_error(
            e,
            context={"instrument_symbol": symbol, "market_type": MarketType.EQUITY.value},
        )


@analyze_app.command("options")
@async_command
async def analyze_options(
    ctx: typer.Context,
    underlying_symbol: str = typer.Argument(..., help="Underlying symbol"),
    expiration: list[str] | None = typer.Option(
        None,
        "--expiration",
        "-e",
        help="Optional expiration date(s) in YYYY-MM-DD format; repeat the flag for multiple dates",
    ),
    option_side: OptionSide = typer.Option(
        OptionSide.ALL,
        "--side",
        help="Options side context",
    ),
    timeframe: JobTimeframe | None = typer.Option(
        None,
        help="Analysis timeframe. Defaults to short_term.",
    ),
    question: str | None = typer.Option(
        None,
        "--question",
        "-q",
        help="Optional question. Providing a question triggers question-driven analysis in auto mode.",
    ),
    mode: AnalyzeMode = typer.Option(
        AnalyzeMode.AUTO,
        "--mode",
        help="Execution mode: auto, deterministic, or question_driven",
    ),
    profile_id: UUID | None = typer.Option(None, help="Profile ID for context (optional)"),
    include_prompt_in_results: bool = typer.Option(
        False,
        "--include-prompt",
        help="Include rendered prompts in the saved results for question-driven runs",
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Bypass data/tool cache reads and writes for this run",
    ),
) -> None:
    """Analyze options with deterministic or question-driven execution.

    Expirations: omit ``--expiration`` / ``-e`` to use the provider default expiry. Pass
    ``-e YYYY-MM-DD`` once per expiry to analyze multiple dates in one run (merged with
    ``expiration_dates`` in the library API). Deterministic multi-expiry results include
    ``multi_expiration`` and per-expiry blocks; question-driven runs pass all expiries in
    context for the agent.
    """
    console = Console()
    final_profile_id = await ensure_profile_with_literacy(profile_id)
    use_case: AnalyzeInstrumentUseCase = get_container().analyze_instrument_use_case()
    json_output = bool(ctx.obj and ctx.obj.get("json_output"))
    stream_flag = bool(ctx.obj and ctx.obj.get("stream")) and not json_output
    request = AnalyzeInstrumentRequest(
        symbol=underlying_symbol,
        market_type=MarketType.OPTIONS,
        timeframe=timeframe,
        question=question,
        mode=mode,
        expiration_date=None,
        expiration_dates=expiration,
        option_side=option_side,
        profile_id=final_profile_id,
        include_prompt_in_results=include_prompt_in_results,
        stream=stream_flag,
        run_id=None,
        no_cache=no_cache,
    )
    try:
        status_text = (
            "[bold blue]Analyzing options with tools...[/bold blue]"
            if request.question
            else "[bold blue]Analyzing options...[/bold blue]"
        )
        if stream_flag and request.question:
            console.print("[dim]Streaming (question-driven)…[/dim]\n")
            response = await use_case.execute(request)
            console.print()
        else:
            with console.status(status_text):
                response = await use_case.execute(request)
        render_run_job_results(response, json_output=json_output)
    except Exception as e:
        handle_cli_error(
            e,
            context={
                "instrument_symbol": underlying_symbol,
                "market_type": MarketType.OPTIONS.value,
                "expiration_dates": expiration,
            },
        )


@analyze_app.command("macro")
@async_command
async def analyze_macro(
    ctx: typer.Context,
    market_index: str = typer.Option(
        "SPY",
        "--market-index",
        "-m",
        help="Reference index for trend/volatility and sector comparison (e.g. SPY, QQQ, DIA). "
        "Breadth and rotation always use the 11 S&P sector ETFs (XLK, XLE, ...) and VIX.",
    ),
    timeframe: JobTimeframe = typer.Option(
        JobTimeframe.MID_TERM,
        help="Analysis timeframe context",
    ),
    question: str | None = typer.Option(
        None,
        "--question",
        "-q",
        help="Optional question. Providing a question triggers question-driven analysis in auto mode.",
    ),
    mode: AnalyzeMode = typer.Option(
        AnalyzeMode.AUTO,
        "--mode",
        help="Execution mode: auto, deterministic, or question_driven",
    ),
    lookback_days: int = typer.Option(
        252,
        "--lookback-days",
        "-d",
        help="Number of days to look back. Default: 252",
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
        help="Include interest rates analysis",
    ),
    include_credit: bool = typer.Option(
        True,
        "--include-credit/--no-include-credit",
        help="Include credit spreads analysis",
    ),
    include_commodities: bool = typer.Option(
        True,
        "--include-commodities/--no-include-commodities",
        help="Include commodities and energy analysis",
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
        help="Include consumer spending and confidence indicators",
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
    profile_id: UUID | None = typer.Option(None, help="Profile ID for context (optional)"),
    include_prompt_in_results: bool = typer.Option(
        False,
        "--include-prompt",
        help="Include rendered prompts in the saved results for question-driven runs",
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Bypass data/tool cache reads and writes for this run",
    ),
) -> None:
    """Analyze the broader market with deterministic or question-driven execution.

    The --market-index (e.g. SPY, QQQ, DIA) is the reference index: it is used for
    trend/volatility detection and as the benchmark for sector comparison. VIX and
    the 11 S&P sector ETFs (XLK, XLE, XLI, XLV, XLF, XLP, XLY, XLU, XLB, XLC, XLRE)
    are always fetched for breadth and rotation; they do not change with --market-index.
    """
    console = Console()
    final_profile_id = await ensure_profile_with_literacy(profile_id)
    use_case: AnalyzeMarketUseCase = get_container().analyze_market_use_case()
    json_output = bool(ctx.obj and ctx.obj.get("json_output"))
    stream_flag = bool(ctx.obj and ctx.obj.get("stream")) and not json_output
    request = AnalyzeMarketRequest(
        market_index=market_index,
        timeframe=timeframe,
        question=question,
        mode=mode,
        lookback_days=lookback_days,
        include_vix=include_vix,
        include_market_breadth=include_market_breadth,
        include_sector_rotation=include_sector_rotation,
        include_rates=include_rates,
        include_credit=include_credit,
        include_commodities=include_commodities,
        include_labor=include_labor,
        include_housing=include_housing,
        include_manufacturing=include_manufacturing,
        include_consumer=include_consumer,
        include_global=include_global,
        include_advanced=include_advanced,
        profile_id=final_profile_id,
        include_prompt_in_results=include_prompt_in_results,
        stream=stream_flag,
        run_id=None,
        no_cache=no_cache,
    )
    try:
        status_text = (
            "[bold blue]Analyzing the market with tools...[/bold blue]"
            if request.question
            else "[bold blue]Running market analysis...[/bold blue]"
        )
        if stream_flag and request.question:
            console.print("[dim]Streaming (question-driven)…[/dim]\n")
            response = await use_case.execute(request)
            console.print()
        else:
            with console.status(status_text):
                response = await use_case.execute(request)
        render_run_job_results(response, json_output=json_output)
    except Exception as e:
        handle_cli_error(e, context={"scope": "market", "market_index": market_index})
