"""Use case container configuration."""

from dependency_injector import providers

from copinance_os.ai.llm.config import LLMConfig
from copinance_os.ai.llm.resources import PromptManager
from copinance_os.core.execution_engine.factory import AnalysisExecutorFactory
from copinance_os.core.orchestrator.research_orchestrator import ResearchOrchestrator
from copinance_os.core.orchestrator.run_job import DefaultJobRunner
from copinance_os.research.workflows.fundamentals import GetStockFundamentalsUseCase
from copinance_os.research.workflows.market import (
    GetHistoricalDataUseCase,
    GetInstrumentUseCase,
    GetOptionsChainUseCase,
    GetQuoteUseCase,
    SearchInstrumentsUseCase,
)
from copinance_os.research.workflows.profile import (
    CreateProfileUseCase,
    DeleteProfileUseCase,
    GetCurrentProfileUseCase,
    GetProfileUseCase,
    ListProfilesUseCase,
    SetCurrentProfileUseCase,
)


def configure_profile_use_cases(
    profile_repository: providers.Provider,
    current_profile: providers.Provider,
    profile_management_service: providers.Provider,
) -> dict[str, providers.Provider]:
    """Profile-only use cases (no market, fundamentals, or LLM dependencies)."""

    create_profile_use_case = providers.Factory(
        CreateProfileUseCase,
        profile_repository=profile_repository,
        profile_service=profile_management_service,
        current_profile=current_profile,
    )

    get_current_profile_use_case = providers.Factory(
        GetCurrentProfileUseCase,
        profile_repository=profile_repository,
        current_profile=current_profile,
    )

    set_current_profile_use_case = providers.Factory(
        SetCurrentProfileUseCase,
        profile_repository=profile_repository,
        profile_service=profile_management_service,
        current_profile=current_profile,
    )

    delete_profile_use_case = providers.Factory(
        DeleteProfileUseCase,
        profile_repository=profile_repository,
        profile_service=profile_management_service,
        current_profile=current_profile,
    )

    get_profile_use_case = providers.Factory(
        GetProfileUseCase,
        profile_repository=profile_repository,
    )

    list_profiles_use_case = providers.Factory(
        ListProfilesUseCase,
        profile_repository=profile_repository,
    )

    return {
        "create_profile_use_case": create_profile_use_case,
        "get_current_profile_use_case": get_current_profile_use_case,
        "set_current_profile_use_case": set_current_profile_use_case,
        "delete_profile_use_case": delete_profile_use_case,
        "get_profile_use_case": get_profile_use_case,
        "list_profiles_use_case": list_profiles_use_case,
    }


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
    """Configure market and analysis use case providers (excludes profile CRUD; see ``configure_profile_use_cases``).

    Args:
        stock_repository: Stock repository provider
        profile_repository: Analysis profile repository provider (for job runner / orchestration)
        current_profile: Current profile provider
        market_data_provider: Market data provider
        fundamental_data_provider: Fundamental data provider
        sec_filings_provider: SEC / EDGAR provider (edgartools) for agent filing tools
        macro_data_provider: Macro data provider
        cache_manager: Cache manager provider
        profile_management_service: Profile management service provider
        llm_config: Optional LLM configuration. If None, question-driven analysis will not be available.
        prompt_manager: Prompt manager for question-driven analysis. If None, a default is used.

    Returns:
        Dictionary of use case providers
    """
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
