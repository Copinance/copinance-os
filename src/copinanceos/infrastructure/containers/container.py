"""Main dependency injection container configuration.

This module composes all container modules into a single Container class.
It replaces the global state pattern with proper dependency injection for better
testability and lifecycle management.
"""

from dependency_injector import containers, providers

from copinanceos.infrastructure.analyzers.llm.config import LLMConfig
from copinanceos.infrastructure.analyzers.llm.config_loader import load_llm_config_from_env
from copinanceos.infrastructure.containers.data_providers import configure_data_providers
from copinanceos.infrastructure.containers.repositories import configure_repositories
from copinanceos.infrastructure.containers.services import configure_services
from copinanceos.infrastructure.containers.storage import configure_storage
from copinanceos.infrastructure.containers.use_cases import configure_use_cases


class Container(containers.DeclarativeContainer):
    """Dependency injection container for Copinance OS.

    This container composes providers from modular configuration modules:
    - Storage backend
    - Repositories
    - Domain services
    - Data providers
    - Use cases

    To use LLM features, provide llm_config when creating the container:
        from copinanceos.infrastructure.analyzers.llm.config import LLMConfig
        from copinanceos.infrastructure.containers import get_container

        llm_config = LLMConfig(
            provider="gemini",
            api_key="your-api-key",
            model="gemini-1.5-pro"
        )
        container = get_container(llm_config=llm_config)

    Or override after creation:
        container = Container()
        container.llm_config.override(llm_config)
    """

    # Configuration
    config = providers.Configuration()
    llm_config = providers.Configuration()

    # Storage backend (singleton, configured from settings)
    storage_backend = configure_storage()

    # Repositories (singletons, use shared storage backend)
    # Note: We need to assign providers directly, not from dict
    # So we'll call configure_repositories and assign individually
    _repositories_config = configure_repositories(storage_backend)
    stock_repository = _repositories_config["stock_repository"]
    research_repository = _repositories_config["research_repository"]
    research_profile_repository = _repositories_config["research_profile_repository"]
    current_profile = _repositories_config["current_profile"]

    # Domain services
    _services_config = configure_services(research_profile_repository)
    profile_management_service = _services_config["profile_management_service"]

    # Data providers (singletons, can be overridden)
    _data_providers_config = providers.Callable(
        configure_data_providers,
        llm_config=llm_config,
    )
    market_data_provider = providers.Callable(
        lambda config: config["market_data_provider"](),
        config=_data_providers_config,
    )
    fundamental_data_provider = providers.Callable(
        lambda config: config["fundamental_data_provider"](),
        config=_data_providers_config,
    )
    sec_filings_provider = providers.Callable(
        lambda config: config["sec_filings_provider"](),
        config=_data_providers_config,
    )
    cache_manager = providers.Callable(
        lambda config: config["cache_manager"](),
        config=_data_providers_config,
    )
    llm_analyzer = providers.Callable(
        lambda config: config["llm_analyzer"](),
        config=_data_providers_config,
    )
    llm_analyzer_for_workflow = providers.Callable(
        lambda config: config["llm_analyzer_for_workflow"](),
        config=_data_providers_config,
    )

    # Use cases
    _use_cases_config = providers.Callable(
        configure_use_cases,
        stock_repository=stock_repository,
        research_repository=research_repository,
        research_profile_repository=research_profile_repository,
        current_profile=current_profile,
        market_data_provider=market_data_provider,
        fundamental_data_provider=fundamental_data_provider,
        sec_filings_provider=sec_filings_provider,
        cache_manager=cache_manager,
        profile_management_service=profile_management_service,
        llm_config=llm_config,
    )
    get_stock_use_case = providers.Callable(
        lambda config: config["get_stock_use_case"](),
        config=_use_cases_config,
    )
    search_stocks_use_case = providers.Callable(
        lambda config: config["search_stocks_use_case"](),
        config=_use_cases_config,
    )
    get_stock_data_use_case = providers.Callable(
        lambda config: config["get_stock_data_use_case"](),
        config=_use_cases_config,
    )
    create_research_use_case = providers.Callable(
        lambda config: config["create_research_use_case"](),
        config=_use_cases_config,
    )
    get_research_use_case = providers.Callable(
        lambda config: config["get_research_use_case"](),
        config=_use_cases_config,
    )
    set_research_context_use_case = providers.Callable(
        lambda config: config["set_research_context_use_case"](),
        config=_use_cases_config,
    )
    create_profile_use_case = providers.Callable(
        lambda config: config["create_profile_use_case"](),
        config=_use_cases_config,
    )
    get_current_profile_use_case = providers.Callable(
        lambda config: config["get_current_profile_use_case"](),
        config=_use_cases_config,
    )
    set_current_profile_use_case = providers.Callable(
        lambda config: config["set_current_profile_use_case"](),
        config=_use_cases_config,
    )
    delete_profile_use_case = providers.Callable(
        lambda config: config["delete_profile_use_case"](),
        config=_use_cases_config,
    )
    get_profile_use_case = providers.Callable(
        lambda config: config["get_profile_use_case"](),
        config=_use_cases_config,
    )
    list_profiles_use_case = providers.Callable(
        lambda config: config["list_profiles_use_case"](),
        config=_use_cases_config,
    )
    research_stock_fundamentals_use_case = providers.Callable(
        lambda config: config["research_stock_fundamentals_use_case"](),
        config=_use_cases_config,
    )
    workflow_executors = providers.Callable(
        lambda config: config["workflow_executors"](),
        config=_use_cases_config,
    )
    execute_research_use_case = providers.Callable(
        lambda config: config["execute_research_use_case"](),
        config=_use_cases_config,
    )


# Global container instance (can be overridden for testing)
_container: Container | None = None


def get_container(llm_config: LLMConfig | None = None, load_from_env: bool = True) -> Container:
    """Get the global dependency injection container.

    Args:
        llm_config: Optional LLM configuration. If None and load_from_env is True,
                   will attempt to load from environment variables.
        load_from_env: If True and llm_config is None, attempt to load LLM config
                      from environment variables (for CLI backward compatibility).

    Returns:
        Container instance
    """
    global _container
    if _container is None:
        container_instance = Container()

        # Load LLM config if not provided
        if llm_config is None and load_from_env:
            llm_config = load_llm_config_from_env()

        if llm_config is not None:
            container_instance.llm_config.override(llm_config)

        _container = container_instance
    return _container


def set_container(container: Container) -> None:
    """Set a custom container (useful for testing).

    Args:
        container: Container instance to use
    """
    global _container
    _container = container


def reset_container() -> None:
    """Reset the global container (useful for testing)."""
    global _container
    _container = None


# Expose container instance for convenience
# Note: For CLI usage, this will be initialized with LLM config from env if available
# For library integrators, use get_container(llm_config=your_config) instead
container = get_container()
