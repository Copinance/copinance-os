"""Generic natural-language entry: question-driven market analysis (full agentic tool suite)."""

from __future__ import annotations

from rich.console import Console

from copinance_os.domain.models.analysis import AnalyzeMarketRequest, AnalyzeMode
from copinance_os.domain.models.job import JobTimeframe
from copinance_os.interfaces.cli.shared.container_access import get_container
from copinance_os.interfaces.cli.shared.error_handler import handle_cli_error
from copinance_os.interfaces.cli.shared.profile_context import ensure_profile_with_literacy
from copinance_os.interfaces.cli.shared.run_job_output import render_run_job_results
from copinance_os.research.workflows.analyze import AnalyzeMarketUseCase


async def run_generic_research(
    question: str,
    *,
    json_output: bool = False,
    include_prompt_in_results: bool = False,
    stream: bool = False,
) -> None:
    """Run the same path as ``copinance analyze macro --question`` with default macro context.

    Uses market scope so the question is not prefixed with a mandatory equity symbol; the model
    selects tools (fundamentals, market data, macro, SEC when configured) from the user question.
    """
    console = Console()
    final_profile_id = await ensure_profile_with_literacy(None)
    use_case: AnalyzeMarketUseCase = get_container().analyze_market_use_case()
    request = AnalyzeMarketRequest(
        market_index="SPY",
        timeframe=JobTimeframe.MID_TERM,
        question=question,
        mode=AnalyzeMode.AUTO,
        lookback_days=252,
        include_vix=True,
        include_market_breadth=True,
        include_sector_rotation=True,
        include_rates=True,
        include_credit=True,
        include_commodities=True,
        include_labor=True,
        include_housing=True,
        include_manufacturing=True,
        include_consumer=True,
        include_global=True,
        include_advanced=True,
        profile_id=final_profile_id,
        include_prompt_in_results=include_prompt_in_results,
        stream=stream and not json_output,
        no_cache=False,
    )
    try:
        if stream and not json_output:
            console.print("[dim]Streaming (question-driven)…[/dim]\n")
            response = await use_case.execute(request)
            console.print()
        else:
            with console.status("[bold blue]Research (question-driven)..."):
                response = await use_case.execute(request)
        render_run_job_results(response, json_output=json_output)
    except Exception as e:
        handle_cli_error(e, context={"entry": "generic_research", "question": question[:200]})
