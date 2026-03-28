"""Analyze CLI: progressive instrument and market analysis."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import typer
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from copinance_os.domain.models.job import JobTimeframe
from copinance_os.domain.models.market import MarketType, OptionSide
from copinance_os.infra.config import get_storage_path_safe
from copinance_os.infra.di import container
from copinance_os.interfaces.cli.error_handler import handle_cli_error
from copinance_os.interfaces.cli.formatting import format_price, format_volume
from copinance_os.interfaces.cli.profile_context import ensure_profile_with_literacy
from copinance_os.interfaces.cli.utils import async_command, save_analysis_results
from copinance_os.research.workflows.analyze import (
    AnalyzeInstrumentRequest,
    AnalyzeInstrumentUseCase,
    AnalyzeMarketRequest,
    AnalyzeMarketUseCase,
    AnalyzeMode,
)

analyze_app = typer.Typer(
    help="Run progressive analysis. Without a question it runs deterministic analysis; with a question it runs tool-using question-driven analysis."
)
console = Console()


# Keys we show in the run-info panel (metadata); rest are internal or shown elsewhere.
_RUN_INFO_KEYS = (
    "execution_type",
    "scope",
    "market_type",
    "instrument_symbol",
    "market_index",
    "timeframe",
    "execution_mode",
    "execution_timestamp",
    "iterations",
    "llm_provider",
    "llm_model",
    "llm_usage",
    "tools_used",
    "status",
    "message",
)


def _is_options_analysis_dict(obj: Any) -> bool:
    """True if obj looks like the options deterministic analysis payload."""
    if not isinstance(obj, dict):
        return False
    return "metrics" in obj and "contracts_analyzed" in obj and "at_the_money_contract" in obj


def _render_options_analysis_tables(analysis: dict[str, Any]) -> Group:
    """Build Rich tables for options analysis dict (summary, metrics, ATM contract)."""
    tables: list[Table] = []

    # Summary table
    summary = Table(title="Summary", show_header=False)
    summary.add_column("Field", style="cyan")
    summary.add_column("Value", style="green")
    for key in ("symbol", "timeframe", "expiration_date", "side", "contracts_analyzed"):
        if key in analysis:
            val = analysis[key]
            summary.add_row(key.replace("_", " ").title(), str(val))
    tables.append(summary)

    # Metrics table
    metrics = analysis.get("metrics") or {}
    if metrics:
        mt = Table(title="Metrics")
        mt.add_column("Metric", style="cyan")
        mt.add_column("Value", justify="right", style="green")
        for label, key in [
            ("Underlying price", "underlying_price"),
            ("Total open interest", "total_open_interest"),
            ("Total volume", "total_volume"),
            ("Avg implied volatility", "average_implied_volatility"),
            ("Put/Call OI ratio", "put_call_open_interest_ratio"),
        ]:
            v = metrics.get(key)
            if v is not None:
                if key in ("total_open_interest", "total_volume"):
                    mt.add_row(label, format_volume(v))
                elif key == "underlying_price":
                    mt.add_row(label, format_price(v))
                elif key == "average_implied_volatility":
                    try:
                        fv = float(v)
                        mt.add_row(label, f"{fv:.2%}")
                    except (TypeError, ValueError):
                        mt.add_row(label, str(v))
                elif key == "put_call_open_interest_ratio":
                    try:
                        mt.add_row(label, f"{float(v):.4f}")
                    except (TypeError, ValueError):
                        mt.add_row(label, str(v))
                elif isinstance(v, (int, float)):
                    mt.add_row(
                        label, f"{float(v):.4f}" if 0 < abs(float(v)) < 10 else f"{float(v):.2f}"
                    )
                else:
                    mt.add_row(label, str(v))
        tables.append(mt)

    # At-the-money contract table
    atm = analysis.get("at_the_money_contract")
    if atm and isinstance(atm, dict):
        atm_table = Table(title="At-the-money contract")
        atm_table.add_column("Field", style="cyan")
        atm_table.add_column("Value", justify="right", style="green")
        for label, key in [
            ("Contract", "contract_symbol"),
            ("Side", "side"),
            ("Strike", "strike"),
            ("Last price", "last_price"),
            ("Implied vol", "implied_volatility"),
            ("Open interest", "open_interest"),
            ("Volume", "volume"),
        ]:
            v = atm.get(key)
            if v is not None:
                if key == "last_price":
                    atm_table.add_row(label, format_price(v))
                elif key in ("open_interest", "volume"):
                    atm_table.add_row(label, format_volume(v))
                elif key == "implied_volatility":
                    try:
                        atm_table.add_row(label, f"{float(v):.2%}")
                    except (TypeError, ValueError):
                        atm_table.add_row(label, str(v))
                else:
                    atm_table.add_row(label, str(v))
        tables.append(atm_table)

    return Group(*tables)


def _render_market_analysis_summary(results: dict[str, Any]) -> Group | None:
    """Build a concise console summary from market_regime_indicators when present."""
    mri = results.get("market_regime_indicators")
    if not mri or not mri.get("success") or not isinstance(mri.get("data"), dict):
        return None
    data = mri["data"]
    parts: list[Table] = []

    # VIX
    vix = data.get("vix")
    if isinstance(vix, dict) and vix.get("available"):
        t = Table(title="VIX", show_header=False)
        t.add_column("Metric", style="cyan")
        t.add_column("Value", style="green")
        if "current_vix" in vix:
            t.add_row("Current", f"{vix['current_vix']:.2f}")
        if "regime" in vix:
            t.add_row("Regime", str(vix["regime"]))
        if "sentiment" in vix:
            t.add_row("Sentiment", str(vix["sentiment"]))
        if "recent_average_20d" in vix:
            t.add_row("20d avg", f"{vix['recent_average_20d']:.2f}")
        parts.append(t)

    # Market breadth
    breadth = data.get("market_breadth")
    if isinstance(breadth, dict) and breadth.get("available"):
        t = Table(title="Market breadth", show_header=False)
        t.add_column("Metric", style="cyan")
        t.add_column("Value", style="green")
        if "breadth_ratio" in breadth:
            t.add_row("Breadth ratio %", f"{breadth['breadth_ratio']:.1f}")
        if "participation_ratio" in breadth:
            t.add_row("Participation %", f"{breadth['participation_ratio']:.1f}")
        if "regime" in breadth:
            t.add_row("Regime", str(breadth["regime"]))
        if "sectors_above_50ma" in breadth and "total_sectors_analyzed" in breadth:
            t.add_row(
                "Sectors above 50d MA",
                f"{breadth['sectors_above_50ma']} / {breadth['total_sectors_analyzed']}",
            )
        parts.append(t)

    # Sector rotation
    rot = data.get("sector_rotation")
    if isinstance(rot, dict) and rot.get("available"):
        t = Table(title="Sector rotation", show_header=False)
        t.add_column("Metric", style="cyan")
        t.add_column("Value", style="green")
        if "rotation_theme" in rot:
            t.add_row("Theme", str(rot["rotation_theme"]))
        leading = rot.get("leading_sectors") or []
        lagging = rot.get("lagging_sectors") or []
        if leading:
            t.add_row(
                "Leading (top 3)",
                ", ".join(s.get("name", s.get("symbol", "")) for s in leading[:3]),
            )
        if lagging:
            t.add_row(
                "Lagging (top 3)",
                ", ".join(s.get("name", s.get("symbol", "")) for s in lagging[:3]),
            )
        parts.append(t)

    if not parts:
        return None
    return Group(*parts)


def _render_results(response: Any) -> None:
    if not response.success:
        console.print("\n✗ Failed", style="bold red")
        console.print(f"Error: {response.error_message}")
        return

    console.print("\n✓ Completed", style="bold green")
    if response.results:
        results = response.results
        saved = save_analysis_results(results, get_storage_path_safe())
        printed_saved_path = False

        # Run info (above results): tool calls count + execution metadata
        tool_calls = results.get("tool_calls")
        tool_calls_line = f"Tool calls: {len(tool_calls)}" if tool_calls else ""
        run_lines = []
        for key in _RUN_INFO_KEYS:
            if key not in results:
                continue
            value = results[key]
            if isinstance(value, dict) and key == "llm_usage":
                # Token counts: input_tokens, output_tokens, total_tokens
                parts = [f"{k}: {v}" for k, v in value.items() if isinstance(v, (int, float))]
                value = ", ".join(parts) if parts else value
            elif isinstance(value, list):
                value = value if len(value) <= 8 else value[:8] + [f"...+{len(value) - 8} more"]
            run_lines.append(f"  [cyan]{key}[/cyan]: {value}")
        if tool_calls_line:
            run_lines.insert(0, f"  [cyan]tool_calls_count[/cyan]: {len(tool_calls)}")
        run_body = "\n".join(run_lines) if run_lines else "  (no metadata)"
        console.print(
            Panel(
                run_body,
                title="[bold]Run info[/bold]",
                border_style="dim",
                padding=(0, 1),
            )
        )
        if "iterations" in results or tool_calls:
            console.print(
                "[dim]iterations: number of LLM reasoning rounds (each round can include tool calls and a response).[/dim]"
            )
        if "llm_usage" in results and results["llm_usage"]:
            console.print(
                "[dim]llm_usage: token counts for this run (input_tokens, output_tokens, total_tokens).[/dim]"
            )

        # Market analysis: show key indicators in console; full data is in the saved file
        market_summary = _render_market_analysis_summary(results)
        if market_summary is not None:
            console.print(
                Panel(
                    market_summary,
                    title="[bold]Market regime summary[/bold]",
                    border_style="green",
                    padding=(1, 2),
                )
            )
            if saved:
                console.print(
                    "[dim]Full indicators, sector details, rates, and time series are in the saved file.[/dim]"
                )
                console.print(f"Results saved to [cyan]{saved}[/cyan]")
                printed_saved_path = True

        # Analysis: tabular for options dict, Markdown for string
        analysis = results.get("analysis")
        if analysis:
            if _is_options_analysis_dict(analysis):
                console.print(
                    Panel(
                        _render_options_analysis_tables(analysis),
                        title="[bold]Analysis[/bold]",
                        border_style="green",
                        padding=(1, 2),
                    )
                )
            elif isinstance(analysis, dict):
                # Generic dict: key-value table
                gen = Table(title="Analysis", show_header=False)
                gen.add_column("Key", style="cyan")
                gen.add_column("Value", style="green")
                for k, v in sorted(analysis.items()):
                    gen.add_row(k, str(v)[:200] + ("..." if len(str(v)) > 200 else ""))
                console.print(
                    Panel(gen, title="[bold]Analysis[/bold]", border_style="green", padding=(1, 2))
                )
            else:
                analysis_text = str(analysis).strip()
                renderable = Markdown(analysis_text) if analysis_text else analysis_text
                console.print(
                    Panel(
                        renderable,
                        title="[bold]Analysis[/bold]",
                        border_style="green",
                        padding=(1, 2),
                    )
                )
            # Summary shown; full data is in the saved file
            if saved:
                console.print("[dim]Full analysis and tool results are in the saved file.[/dim]")
                if not printed_saved_path:
                    console.print(f"Results saved to [cyan]{saved}[/cyan]")
                    printed_saved_path = True

        if saved and not printed_saved_path:
            console.print(f"Results saved to [cyan]{saved}[/cyan]")


@analyze_app.command("equity")
@async_command
async def analyze_equity(
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
) -> None:
    """Analyze an equity with deterministic or question-driven execution."""
    final_profile_id = await ensure_profile_with_literacy(profile_id)
    use_case: AnalyzeInstrumentUseCase = container.analyze_instrument_use_case()
    request = AnalyzeInstrumentRequest(
        symbol=symbol,
        market_type=MarketType.EQUITY,
        timeframe=timeframe,
        question=question,
        mode=mode,
        expiration_date=None,
        option_side=OptionSide.ALL,
        profile_id=final_profile_id,
        include_prompt_in_results=include_prompt_in_results,
    )
    try:
        status_text = (
            "[bold blue]Analyzing equity with tools...[/bold blue]"
            if request.question
            else "[bold blue]Analyzing equity...[/bold blue]"
        )
        with console.status(status_text):
            response = await use_case.execute(request)
        _render_results(response)
    except Exception as e:
        handle_cli_error(
            e,
            context={"instrument_symbol": symbol, "market_type": MarketType.EQUITY.value},
        )


@analyze_app.command("options")
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
) -> None:
    """Analyze options with deterministic or question-driven execution."""
    final_profile_id = await ensure_profile_with_literacy(profile_id)
    use_case: AnalyzeInstrumentUseCase = container.analyze_instrument_use_case()
    request = AnalyzeInstrumentRequest(
        symbol=underlying_symbol,
        market_type=MarketType.OPTIONS,
        timeframe=timeframe,
        question=question,
        mode=mode,
        expiration_date=expiration_date,
        option_side=option_side,
        profile_id=final_profile_id,
        include_prompt_in_results=include_prompt_in_results,
    )
    try:
        status_text = (
            "[bold blue]Analyzing options with tools...[/bold blue]"
            if request.question
            else "[bold blue]Analyzing options...[/bold blue]"
        )
        with console.status(status_text):
            response = await use_case.execute(request)
        _render_results(response)
    except Exception as e:
        handle_cli_error(
            e,
            context={
                "instrument_symbol": underlying_symbol,
                "market_type": MarketType.OPTIONS.value,
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
) -> None:
    """Analyze the broader market with deterministic or question-driven execution.

    The --market-index (e.g. SPY, QQQ, DIA) is the reference index: it is used for
    trend/volatility detection and as the benchmark for sector comparison. VIX and
    the 11 S&P sector ETFs (XLK, XLE, XLI, XLV, XLF, XLP, XLY, XLU, XLB, XLC, XLRE)
    are always fetched for breadth and rotation; they do not change with --market-index.
    """
    final_profile_id = await ensure_profile_with_literacy(profile_id)
    use_case: AnalyzeMarketUseCase = container.analyze_market_use_case()
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
    )
    try:
        status_text = (
            "[bold blue]Analyzing the market with tools...[/bold blue]"
            if request.question
            else "[bold blue]Running market analysis...[/bold blue]"
        )
        with console.status(status_text):
            response = await use_case.execute(request)
        _render_results(response)
    except Exception as e:
        handle_cli_error(e, context={"scope": "market", "market_index": market_index})
