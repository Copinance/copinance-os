"""Use case container configuration."""

from dependency_injector import providers

from copinanceos.application.use_cases.fundamentals import (
    ResearchStockFundamentalsUseCase,
)
from copinanceos.application.use_cases.profile import (
    CreateProfileUseCase,
    DeleteProfileUseCase,
    GetCurrentProfileUseCase,
    GetProfileUseCase,
    ListProfilesUseCase,
    SetCurrentProfileUseCase,
)
from copinanceos.application.use_cases.research import (
    CreateResearchUseCase,
    ExecuteResearchUseCase,
    GetResearchUseCase,
    SetResearchContextUseCase,
)
from copinanceos.application.use_cases.stock import (
    GetStockDataUseCase,
    GetStockUseCase,
    SearchStocksUseCase,
)
from copinanceos.infrastructure.analyzers.llm.config import LLMConfig
from copinanceos.infrastructure.factories import WorkflowExecutorFactory


def configure_use_cases(
    stock_repository: providers.Provider,
    research_repository: providers.Provider,
    research_profile_repository: providers.Provider,
    current_profile: providers.Provider,
    market_data_provider: providers.Provider,
    fundamental_data_provider: providers.Provider,
    sec_filings_provider: providers.Provider,
    cache_manager: providers.Provider,
    profile_management_service: providers.Provider,
    llm_config: LLMConfig | None = None,
) -> dict[str, providers.Provider]:
    """Configure use case providers.

    Args:
        stock_repository: Stock repository provider
        research_repository: Research repository provider
        research_profile_repository: Research profile repository provider
        current_profile: Current profile provider
        market_data_provider: Market data provider
        fundamental_data_provider: Fundamental data provider
        sec_filings_provider: SEC filings provider
        cache_manager: Cache manager provider
        profile_management_service: Profile management service provider
        llm_config: Optional LLM configuration. If None, agentic workflows will not be available.

    Returns:
        Dictionary of use case providers
    """
    # Stock use cases
    get_stock_use_case = providers.Factory(
        GetStockUseCase,
        stock_repository=stock_repository,
    )

    search_stocks_use_case = providers.Factory(
        SearchStocksUseCase,
        stock_repository=stock_repository,
        market_data_provider=market_data_provider,
    )

    get_stock_data_use_case = providers.Factory(
        GetStockDataUseCase,
        stock_repository=stock_repository,
    )

    # Research use cases
    create_research_use_case = providers.Factory(
        CreateResearchUseCase,
        research_repository=research_repository,
    )

    get_research_use_case = providers.Factory(
        GetResearchUseCase,
        research_repository=research_repository,
    )

    set_research_context_use_case = providers.Factory(
        SetResearchContextUseCase,
        research_repository=research_repository,
        profile_repository=research_profile_repository,
    )

    # Profile use cases
    create_profile_use_case = providers.Factory(
        CreateProfileUseCase,
        profile_repository=research_profile_repository,
        profile_service=profile_management_service,
        current_profile=current_profile,
    )

    get_current_profile_use_case = providers.Factory(
        GetCurrentProfileUseCase,
        profile_repository=research_profile_repository,
        current_profile=current_profile,
    )

    set_current_profile_use_case = providers.Factory(
        SetCurrentProfileUseCase,
        profile_repository=research_profile_repository,
        profile_service=profile_management_service,
        current_profile=current_profile,
    )

    delete_profile_use_case = providers.Factory(
        DeleteProfileUseCase,
        profile_repository=research_profile_repository,
        profile_service=profile_management_service,
        current_profile=current_profile,
    )

    get_profile_use_case = providers.Factory(
        GetProfileUseCase,
        profile_repository=research_profile_repository,
    )

    list_profiles_use_case = providers.Factory(
        ListProfilesUseCase,
        profile_repository=research_profile_repository,
    )

    # Fundamentals use case
    research_stock_fundamentals_use_case = providers.Factory(
        ResearchStockFundamentalsUseCase,
        fundamental_data_provider=fundamental_data_provider,
    )

    # Workflow executors (defined after use cases to reference them)
    workflow_executors = providers.Singleton(
        WorkflowExecutorFactory.create_all,
        get_stock_use_case=get_stock_use_case,
        market_data_provider=market_data_provider,
        fundamentals_use_case=research_stock_fundamentals_use_case,
        fundamental_data_provider=fundamental_data_provider,
        sec_filings_provider=sec_filings_provider,
        cache_manager=cache_manager,
        llm_config=llm_config,
    )

    # Execute research use case (defined after workflow_executors)
    execute_research_use_case = providers.Factory(
        ExecuteResearchUseCase,
        research_repository=research_repository,
        profile_repository=research_profile_repository,
        workflow_executors=workflow_executors,
    )

    return {
        "get_stock_use_case": get_stock_use_case,
        "search_stocks_use_case": search_stocks_use_case,
        "get_stock_data_use_case": get_stock_data_use_case,
        "create_research_use_case": create_research_use_case,
        "get_research_use_case": get_research_use_case,
        "set_research_context_use_case": set_research_context_use_case,
        "create_profile_use_case": create_profile_use_case,
        "get_current_profile_use_case": get_current_profile_use_case,
        "set_current_profile_use_case": set_current_profile_use_case,
        "delete_profile_use_case": delete_profile_use_case,
        "get_profile_use_case": get_profile_use_case,
        "list_profiles_use_case": list_profiles_use_case,
        "research_stock_fundamentals_use_case": research_stock_fundamentals_use_case,
        "workflow_executors": workflow_executors,
        "execute_research_use_case": execute_research_use_case,
    }
