"""Research-related CLI commands."""

from enum import Enum
from typing import Any
from uuid import UUID

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel

from copinanceos.application.use_cases.profile import (
    CreateProfileRequest,
    GetCurrentProfileRequest,
)
from copinanceos.application.use_cases.research import (
    CreateResearchRequest,
    ExecuteResearchRequest,
    GetResearchRequest,
    SetResearchContextRequest,
)
from copinanceos.cli.error_handler import handle_cli_error
from copinanceos.cli.utils import async_command
from copinanceos.domain.models.research import ResearchTimeframe
from copinanceos.domain.models.research_profile import FinancialLiteracy
from copinanceos.infrastructure.containers import container

research_app = typer.Typer(help="Research management commands")
console = Console()


class WorkflowType(str, Enum):
    """Supported workflow types (validated by the CLI)."""

    STOCK = "stock"
    MACRO = "macro"
    AGENT = "agent"


async def _ensure_profile_with_literacy(profile_id: UUID | None = None) -> UUID | None:
    """Ensure user has a profile with literacy level for personalized analysis.

    Checks if a profile exists (either provided or current). If no profile exists,
    prompts the user to create one with a financial literacy level.

    Args:
        profile_id: Optional profile ID to check. If None, checks current profile.

    Returns:
        Profile ID if available, None if user declined to create one.
    """
    # If profile_id is provided, assume it's valid (will be validated by use case)
    if profile_id is not None:
        return profile_id

    # Check current profile
    current_profile_uc = container.get_current_profile_use_case()
    current_response = await current_profile_uc.execute(GetCurrentProfileRequest())

    if current_response.profile:
        current_profile_id: UUID = current_response.profile.id
        return current_profile_id

    # No profile exists - prompt user
    console.print("\n[bold yellow]No profile found with financial literacy level[/bold yellow]")
    console.print(
        "Setting your financial literacy level helps provide more personalized analysis results."
    )
    console.print("\nFinancial literacy levels:")
    console.print("  • [cyan]beginner[/cyan]: Simple language, concepts explained")
    console.print("  • [cyan]intermediate[/cyan]: Some technical terms with explanations")
    console.print("  • [cyan]advanced[/cyan]: Technical terminology used freely")

    if typer.confirm("\nWould you like to set your financial literacy level now?", default=True):
        # Prompt for literacy level
        console.print("\nSelect your financial literacy level:")
        console.print("  1. Beginner")
        console.print("  2. Intermediate")
        console.print("  3. Advanced")

        choice = typer.prompt("Enter choice (1-3)", default="2")
        literacy_map = {
            "1": FinancialLiteracy.BEGINNER,
            "2": FinancialLiteracy.INTERMEDIATE,
            "3": FinancialLiteracy.ADVANCED,
        }
        selected_literacy = literacy_map.get(choice, FinancialLiteracy.INTERMEDIATE)

        # Create profile
        create_profile_uc = container.create_profile_use_case()
        create_request = CreateProfileRequest(
            financial_literacy=selected_literacy,
            display_name=None,
        )
        create_response = await create_profile_uc.execute(create_request)

        console.print(
            f"\n✓ Profile created with {selected_literacy.value} literacy level",
            style="bold green",
        )
        new_profile_id: UUID = create_response.profile.id
        return new_profile_id
    else:
        console.print(
            "\n[yellow]Continuing without profile. Analysis will use default settings.[/yellow]"
        )
        return None


def _display_agentic_results(results: dict[str, Any]) -> None:
    """Display agent workflow results in a formatted way."""
    # Show metadata
    if "llm_provider" in results:
        console.print(f"\n[bold cyan]LLM Provider:[/bold cyan] {results['llm_provider']}")
    if "iterations" in results:
        console.print(f"[bold cyan]Iterations:[/bold cyan] {results['iterations']}")
    if "tools_used" in results:
        tools_count = len(results["tools_used"])
        console.print(f"[bold cyan]Tools Used:[/bold cyan] {tools_count}")

    # Show tool calls
    if "tool_calls" in results and results["tool_calls"]:
        console.print("\n[bold]Tool Execution:[/bold]")
        for tool_call in results["tool_calls"]:
            tool_name = tool_call.get("tool", "unknown")
            success = tool_call.get("success", False)
            status_icon = "✓" if success else "✗"
            status_style = "green" if success else "red"
            console.print(f"  [{status_style}]{status_icon}[/{status_style}] {tool_name}")
            if not success and "error" in tool_call:
                console.print(f"    [dim red]Error: {tool_call['error']}[/dim red]")

    # Show analysis
    if "analysis" in results and results["analysis"]:
        analysis_text = results["analysis"]
        console.print("\n[bold]Analysis:[/bold]")
        # Try to format as markdown, fallback to plain text
        try:
            console.print(Panel(Markdown(analysis_text), border_style="blue"))
        except Exception:
            # If markdown parsing fails, just print as text
            console.print(Panel(analysis_text, border_style="blue"))


@research_app.command("create")
@async_command
async def create_research(
    symbol: str = typer.Argument(..., help="Stock symbol"),
    timeframe: ResearchTimeframe = typer.Option(
        ResearchTimeframe.MID_TERM, help="Research timeframe"
    ),
    workflow: WorkflowType = typer.Option(
        WorkflowType.STOCK,
        help="Workflow type",
    ),
    profile_id: UUID | None = typer.Option(None, help="Research profile ID for context"),
) -> None:
    """Create a new research task."""
    # Ensure profile with literacy level exists
    final_profile_id = await _ensure_profile_with_literacy(profile_id)

    use_case = container.create_research_use_case()
    request = CreateResearchRequest(
        stock_symbol=symbol,
        timeframe=timeframe,
        workflow_type=workflow.value,
        profile_id=final_profile_id,
    )
    response = await use_case.execute(request)

    console.print("✓ Research created successfully", style="bold green")
    console.print(f"ID: {response.research.id}")
    console.print(f"Symbol: {response.research.stock_symbol}")
    console.print(f"Timeframe: {response.research.timeframe.value}")
    console.print(f"Workflow: {response.research.workflow_type}")
    console.print(f"Status: {response.research.status.value}")
    if response.research.profile_id:
        console.print(f"Profile ID: {response.research.profile_id}")
        if final_profile_id and final_profile_id != profile_id:
            console.print("  (using current profile)", style="dim")


@research_app.command("run")
@async_command
async def run_research(
    symbol: str = typer.Argument(..., help="Stock symbol"),
    timeframe: ResearchTimeframe = typer.Option(
        ResearchTimeframe.MID_TERM, help="Research timeframe"
    ),
    workflow: WorkflowType = typer.Option(
        WorkflowType.STOCK,
        help="Workflow type",
    ),
    profile_id: UUID | None = typer.Option(None, help="Research profile ID for context"),
    question: str | None = typer.Option(
        None, "--question", "-q", help="Custom question for agent workflows (LLM)"
    ),
) -> None:
    """Create and execute a research workflow in one command (quick testing)."""
    # Ensure profile with literacy level exists
    final_profile_id = await _ensure_profile_with_literacy(profile_id)

    # Create research
    create_use_case = container.create_research_use_case()
    create_request = CreateResearchRequest(
        stock_symbol=symbol,
        timeframe=timeframe,
        workflow_type=workflow.value,
        profile_id=final_profile_id,
    )
    create_response = await create_use_case.execute(create_request)
    research_id = create_response.research.id

    console.print("✓ Research created", style="bold green")
    console.print(f"ID: {research_id}")
    console.print(f"Symbol: {create_response.research.stock_symbol}")
    console.print(f"Workflow: {create_response.research.workflow_type}")
    if create_response.research.profile_id:
        console.print(f"Profile ID: {create_response.research.profile_id}")

    # Prepare execution context
    context: dict[str, Any] = {}
    if question and workflow == WorkflowType.AGENT:
        context["question"] = question
        console.print(f"\n[dim]Question: {question}[/dim]")

    # Execute research
    execute_use_case = container.execute_research_use_case()
    execute_request = ExecuteResearchRequest(research_id=research_id, context=context)

    try:
        with console.status("[bold blue]Executing research workflow..."):
            execute_response = await execute_use_case.execute(execute_request)

        if execute_response.success:
            console.print("\n✓ Research executed successfully", style="bold green")
            console.print(f"Status: {execute_response.research.status.value}")

            results = execute_response.research.results

            # Special formatting for agent workflows
            if workflow == WorkflowType.AGENT and results:
                _display_agentic_results(results)
            else:
                console.print("\n[bold]Results:[/bold]")
                for key, value in results.items():
                    if key not in ["analysis", "tool_calls"]:  # Skip these, shown separately
                        console.print(f"  {key}: {value}")
        else:
            console.print("\n✗ Research execution failed", style="bold red")
            console.print(f"Error: {execute_response.research.error_message}")
    except Exception as e:
        handle_cli_error(e, context={"symbol": symbol, "workflow": workflow.value})


@research_app.command("macro")
@async_command
async def macro_regime(
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
        help="Number of days to look back for analysis. Default: 252 (1 trading year)",
    ),
    include_vix: bool = typer.Option(
        True,
        "--include-vix/--no-include-vix",
        help="Include VIX (volatility index) analysis. Default: enabled",
    ),
    include_market_breadth: bool = typer.Option(
        True,
        "--include-market-breadth/--no-include-market-breadth",
        help="Include equity market breadth indicators (advancing/declining stocks). Default: enabled",
    ),
    include_sector_rotation: bool = typer.Option(
        True,
        "--include-sector-rotation/--no-include-sector-rotation",
        help="Include sector rotation analysis. Default: enabled",
    ),
    include_rates: bool = typer.Option(
        True,
        "--include-rates/--no-include-rates",
        help="Include interest rates analysis (10Y Treasury, yield curve). Uses FRED API if available, falls back to yfinance. Default: enabled",
    ),
    include_credit: bool = typer.Option(
        True,
        "--include-credit/--no-include-credit",
        help="Include credit spread analysis (HYG, LQD spreads). Uses FRED API if available, falls back to yfinance. Default: enabled",
    ),
    include_commodities: bool = typer.Option(
        True,
        "--include-commodities/--no-include-commodities",
        help="Include commodities/energy analysis (oil, natural gas). Uses FRED API if available, falls back to yfinance. Default: enabled",
    ),
) -> None:
    """Run the macro + market regime workflow and print a combined result payload.

    This command combines market regime indicators (VIX, breadth, sector rotation) with
    macroeconomic indicators (rates, credit spreads, commodities) to provide a comprehensive
    view of market conditions.

    Examples:
        # Full analysis with defaults
        copinance research macro

        # Custom index and lookback period
        copinance research macro --market-index QQQ --lookback-days 180

        # Only macro indicators (rates, credit, commodities)
        copinance research macro --no-include-vix --no-include-market-breadth --no-include-sector-rotation

        # Only market regime indicators
        copinance research macro --no-include-rates --no-include-credit --no-include-commodities
    """
    create_use_case = container.create_research_use_case()
    create_request = CreateResearchRequest(
        stock_symbol="MARKET",
        timeframe=ResearchTimeframe.MID_TERM,
        workflow_type="macro",
        profile_id=None,
    )
    create_response = await create_use_case.execute(create_request)
    research_id = create_response.research.id

    console.print("✓ Research created", style="bold green")
    console.print(f"ID: {research_id}")
    console.print("Workflow: macro")

    context: dict[str, Any] = {
        "market_index": market_index.upper(),
        "lookback_days": lookback_days,
        "include_vix": include_vix,
        "include_market_breadth": include_market_breadth,
        "include_sector_rotation": include_sector_rotation,
        "include_rates": include_rates,
        "include_credit": include_credit,
        "include_commodities": include_commodities,
    }

    execute_use_case = container.execute_research_use_case()
    execute_request = ExecuteResearchRequest(research_id=research_id, context=context)

    try:
        with console.status("[bold blue]Running macro + market regime analysis..."):
            execute_response = await execute_use_case.execute(execute_request)

        if execute_response.success:
            console.print("\n✓ Completed", style="bold green")
            results = execute_response.research.results or {}
            console.print("\n[bold]Results:[/bold]")
            for key, value in results.items():
                console.print(f"  {key}: {value}")
        else:
            console.print("\n✗ Failed", style="bold red")
            console.print(f"Error: {execute_response.research.error_message}")
    except Exception as e:
        handle_cli_error(e, context={"workflow": "macro", "market_index": market_index})


@research_app.command("execute")
@async_command
async def execute_research(
    research_id: UUID = typer.Argument(..., help="Research ID"),
    question: str | None = typer.Option(
        None, "--question", "-q", help="Custom question for agent workflows (LLM)"
    ),
) -> None:
    """Execute a research workflow."""
    # Check if research has a profile, if not prompt user
    get_research_uc = container.get_research_use_case()
    get_research_response = await get_research_uc.execute(
        GetResearchRequest(research_id=research_id)
    )

    if get_research_response.research is None:
        console.print("Research not found", style="bold red")
        return

    research = get_research_response.research

    # If research doesn't have a profile, ensure one exists
    if research.profile_id is None:
        profile_id = await _ensure_profile_with_literacy()
        if profile_id:
            # Set profile on research
            set_context_uc = container.set_research_context_use_case()
            await set_context_uc.execute(
                SetResearchContextRequest(research_id=research_id, profile_id=profile_id)
            )

    # Prepare execution context
    context: dict[str, str] = {}
    if question:
        context["question"] = question
        console.print(f"[dim]Question: {question}[/dim]\n")

    use_case = container.execute_research_use_case()
    request = ExecuteResearchRequest(research_id=research_id, context=context)

    try:
        with console.status("[bold blue]Executing research workflow..."):
            response = await use_case.execute(request)

        if response.success:
            console.print("✓ Research executed successfully", style="bold green")
            console.print(f"Status: {response.research.status.value}")

            results = response.research.results

            # Special formatting for agent workflows
            if response.research.workflow_type == "agent" and results:
                _display_agentic_results(results)
            else:
                console.print("\n[bold]Results:[/bold]")
                for key, value in results.items():
                    if key not in ["analysis", "tool_calls"]:
                        console.print(f"  {key}: {value}")
        else:
            console.print("✗ Research execution failed", style="bold red")
            console.print(f"Error: {response.research.error_message}")
    except Exception as e:
        handle_cli_error(e, context={"research_id": str(research_id)})


@research_app.command("get")
@async_command
async def get_research(
    research_id: UUID = typer.Argument(..., help="Research ID"),
) -> None:
    """Get research details."""
    use_case = container.get_research_use_case()
    request = GetResearchRequest(research_id=research_id)
    response = await use_case.execute(request)

    if response.research is None:
        console.print("Research not found", style="bold red")
        return

    research = response.research
    console.print("\n[bold]Research Details[/bold]")
    console.print(f"ID: {research.id}")
    console.print(f"Symbol: {research.stock_symbol}")
    console.print(f"Timeframe: {research.timeframe.value}")
    console.print(f"Workflow: {research.workflow_type}")
    console.print(f"Status: {research.status.value}")

    if research.profile_id:
        console.print(f"Profile ID: {research.profile_id}")

    if research.results:
        console.print("\n[bold]Results:[/bold]")
        for key, value in research.results.items():
            console.print(f"  {key}: {value}")


@research_app.command("set-context")
@async_command
async def set_research_context(
    research_id: UUID = typer.Argument(..., help="Research ID"),
    profile_id: UUID | None = typer.Option(None, help="Profile ID to set (omit to clear context)"),
) -> None:
    """Set or clear research context (profile)."""
    use_case = container.set_research_context_use_case()
    request = SetResearchContextRequest(
        research_id=research_id,
        profile_id=profile_id,
    )

    try:
        response = await use_case.execute(request)
        if profile_id:
            console.print("✓ Research context set successfully", style="bold green")
            console.print(f"Research ID: {response.research.id}")
            console.print(f"Profile ID: {response.research.profile_id}")
        else:
            console.print("✓ Research context cleared", style="bold green")
            console.print(f"Research ID: {response.research.id}")
    except Exception as e:
        handle_cli_error(
            e,
            context={
                "research_id": str(research_id),
                "profile_id": str(profile_id) if profile_id else None,
            },
        )


@research_app.command("ask")
@async_command
async def ask_question(
    question: str = typer.Argument(..., help="Question to ask (about a stock or the market)"),
    symbol: str | None = typer.Option(
        None, "--symbol", "-s", help="Stock symbol (optional for market-wide questions)"
    ),
    timeframe: ResearchTimeframe = typer.Option(
        ResearchTimeframe.MID_TERM, help="Research timeframe"
    ),
    profile_id: UUID | None = typer.Option(None, help="Research profile ID for context"),
) -> None:
    """Quick Q&A: Ask a question about a stock or the market using agent workflow.

    Examples:
      # Market-wide question (no symbol needed)
      copinance research ask "What's the current state of the overall market?"

      # Stock-specific question
      copinance research ask "What's the current state of the overall market?" --symbol AAPL
      copinance research ask "What is Apple's P/E ratio?" --symbol AAPL
    """
    # Ensure profile with literacy level exists
    final_profile_id = await _ensure_profile_with_literacy(profile_id)

    # Use generic placeholder for market-wide questions
    # Research model requires stock_symbol, so we use a placeholder
    research_symbol = symbol.upper() if symbol else "MARKET"
    is_market_wide = symbol is None

    if is_market_wide:
        console.print(f"[bold]Market-wide question:[/bold] {question}\n")
    else:
        console.print(f"[bold]Question about {symbol}:[/bold] {question}\n")

    # Create research
    create_use_case = container.create_research_use_case()
    create_request = CreateResearchRequest(
        stock_symbol=research_symbol,
        timeframe=timeframe,
        workflow_type="agent",
        profile_id=final_profile_id,
    )
    create_response = await create_use_case.execute(create_request)
    research_id = create_response.research.id

    # Execute with question
    execute_use_case = container.execute_research_use_case()
    execute_request = ExecuteResearchRequest(
        research_id=research_id,
        context={"question": question},
    )

    status_message = (
        "[bold blue]Analyzing market and preparing answer..."
        if is_market_wide
        else f"[bold blue]Analyzing {symbol} and preparing answer..."
    )
    with console.status(status_message):
        execute_response = await execute_use_case.execute(execute_request)

    if execute_response.success:
        results = execute_response.research.results
        if results and "analysis" in results:
            _display_agentic_results(results)
        else:
            console.print("\n[bold yellow]No analysis available[/bold yellow]")
            console.print("Results:", results)
    else:
        console.print("\n✗ Failed to get answer", style="bold red")
        console.print(f"Error: {execute_response.research.error_message}")
