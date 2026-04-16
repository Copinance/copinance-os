"""Market / analysis use case configuration.

Heavy dependencies (openai, pandas, edgar, QuantLib, google-genai …) are imported
*inside* ``configure_use_cases`` so that importing this module is nearly free.  The
function is only called when the ``providers.Singleton`` wrapping it is first resolved
— i.e. when an actual market or analysis command runs, not at CLI startup.

Profile use cases live in ``infra.di.profile_use_cases`` (no heavy deps).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dependency_injector import providers

if TYPE_CHECKING:
    from copinance_os.ai.llm.config import LLMConfig
    from copinance_os.ai.llm.resources import PromptManager


def configure_use_cases(
    stock_repository: providers.Provider,
    profile_repository: providers.Provider,
    current_profile: providers.Provider,
    market_data_provider: providers.Provider,
    fundamental_data_provider: providers.Provider,
    sec_filings_provider: providers.Provider,
    macro_data_provider: providers.Provider,
    cache_manager: providers.Provider,
    profile_management_service: providers.Provider,
    llm_config: LLMConfig | None = None,
    prompt_manager: PromptManager | None = None,
) -> dict[str, providers.Provider]:
    """Configure market and analysis use case providers.

    All heavy imports (openai, pandas, google-genai, edgar, yfinance …) live inside
    this function so the module can be imported without triggering them.  The function
    is only executed by ``dependency_injector`` when the first market/analysis provider
    is resolved at runtime.

    Args:
        stock_repository: Stock repository provider
        profile_repository: Analysis profile repository provider
        current_profile: Current profile provider
        market_data_provider: Market data provider
        fundamental_data_provider: Fundamental data provider
        sec_filings_provider: SEC / EDGAR provider
        macro_data_provider: Macro data provider
        cache_manager: Cache manager provider
        profile_management_service: Profile management service provider
        llm_config: Optional LLM configuration.
        prompt_manager: Prompt manager for question-driven analysis.

    Returns:
        Dictionary of use case providers
    """
    # --- deferred heavy imports (openai, pandas, google, edgar, yfinance, QuantLib) ---
    from copinance_os.core.execution_engine.factory import AnalysisExecutorFactory  # noqa: PLC0415
    from copinance_os.core.orchestrator.research_orchestrator import (  # noqa: PLC0415
        ResearchOrchestrator,
    )
    from copinance_os.core.orchestrator.run_job import DefaultJobRunner  # noqa: PLC0415
    from copinance_os.research.workflows.fundamentals import (  # noqa: PLC0415
        GetStockFundamentalsUseCase,
    )
    from copinance_os.research.workflows.market import (  # noqa: PLC0415
        GetHistoricalDataUseCase,
        GetInstrumentUseCase,
        GetOptionsChainUseCase,
        GetQuoteUseCase,
        SearchInstrumentsUseCase,
    )

    # Market instrument use cases
    get_instrument_use_case = providers.Factory(
        GetInstrumentUseCase,
        instrument_repository=stock_repository,
    )

    search_instruments_use_case = providers.Factory(
        SearchInstrumentsUseCase,
        instrument_repository=stock_repository,
        market_data_provider=market_data_provider,
    )

    get_quote_use_case = providers.Factory(
        GetQuoteUseCase,
        market_data_provider=market_data_provider,
    )

    get_historical_data_use_case = providers.Factory(
        GetHistoricalDataUseCase,
        market_data_provider=market_data_provider,
    )

    get_options_chain_use_case = providers.Factory(
        GetOptionsChainUseCase,
        market_data_provider=market_data_provider,
    )

    # Fundamentals use case
    get_stock_fundamentals_use_case = providers.Factory(
        GetStockFundamentalsUseCase,
        fundamental_data_provider=fundamental_data_provider,
    )

    # Analysis executors
    analysis_executors = providers.Singleton(
        AnalysisExecutorFactory.create_all,
        get_instrument_use_case=get_instrument_use_case,
        get_quote_use_case=get_quote_use_case,
        get_historical_data_use_case=get_historical_data_use_case,
        get_options_chain_use_case=get_options_chain_use_case,
        market_data_provider=market_data_provider,
        macro_data_provider=macro_data_provider,
        fundamentals_use_case=get_stock_fundamentals_use_case,
        fundamental_data_provider=fundamental_data_provider,
        sec_filings_provider=sec_filings_provider,
        cache_manager=cache_manager,
        llm_config=llm_config,
        prompt_manager=prompt_manager,
    )

    job_runner = providers.Factory(
        DefaultJobRunner,
        profile_repository=profile_repository,
        analysis_executors=analysis_executors,
    )

    research_orchestrator = providers.Factory(
        ResearchOrchestrator,
        job_runner=job_runner,
    )

    return {
        "get_instrument_use_case": get_instrument_use_case,
        "search_instruments_use_case": search_instruments_use_case,
        "get_quote_use_case": get_quote_use_case,
        "get_historical_data_use_case": get_historical_data_use_case,
        "get_options_chain_use_case": get_options_chain_use_case,
        "get_stock_fundamentals_use_case": get_stock_fundamentals_use_case,
        "analysis_executors": analysis_executors,
        "research_orchestrator": research_orchestrator,
    }
