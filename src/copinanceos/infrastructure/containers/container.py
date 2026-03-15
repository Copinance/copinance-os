"""Main dependency injection container configuration.

This module composes all container modules into a single Container class.
It replaces the global state pattern with proper dependency injection for better
testability and lifecycle management.
"""

from dependency_injector import containers, providers

from copinanceos.application.runners import (
    DefaultAnalyzeInstrumentRunner,
    DefaultAnalyzeMarketRunner,
)
from copinanceos.application.use_cases.analyze import (
    AnalyzeInstrumentUseCase,
    AnalyzeMarketUseCase,
)
from copinanceos.infrastructure.analyzers.llm.config import LLMConfig
from copinanceos.infrastructure.analyzers.llm.config_loader import load_llm_config_from_env
from copinanceos.infrastructure.analyzers.llm.resources import PromptManager
from copinanceos.infrastructure.cache import CacheManager
from copinanceos.infrastructure.config import get_settings
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

    To provide your own FRED API key (for library integrators):
        container = get_container(fred_api_key="your-fred-api-key")

    Or override after creation:
        container = Container()
        container.llm_config.override(llm_config)
        container.fred_api_key_config.override("your-fred-api-key")
    """

    # Configuration
    config = providers.Configuration()
    llm_config = providers.Configuration()
    fred_api_key_config = providers.Configuration()

    # Prompt templates: default manager (package prompts). Override via get_container().
    prompt_manager = providers.Singleton(PromptManager)

    # Storage backend (singleton, configured from settings)
    storage_backend = configure_storage()

    # Repositories (singletons, use shared storage backend)
    # Note: We need to assign providers directly, not from dict
    # So we'll call configure_repositories and assign individually
    _repositories_config = configure_repositories(storage_backend)
    stock_repository = _repositories_config["stock_repository"]
    profile_repository = _repositories_config["profile_repository"]
    current_profile = _repositories_config["current_profile"]

    # Domain services
    _services_config = configure_services(profile_repository)
    profile_management_service = _services_config["profile_management_service"]

    # Data providers (singletons, can be overridden)
    # fred_api_key_config is optional - if not provided, configure_data_providers will use settings
    _data_providers_config = providers.Callable(
        configure_data_providers,
        llm_config=llm_config,
        fred_api_key=providers.Callable(
            lambda key: key if key else None,
            key=fred_api_key_config.provided,
        ),
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
    macro_data_provider = providers.Callable(
        lambda config: config["macro_data_provider"](),
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
    llm_analyzer_for_analysis = providers.Callable(
        lambda config: config["llm_analyzer_for_analysis"](),
        config=_data_providers_config,
    )

    # Use cases
    _use_cases_config = providers.Callable(
        configure_use_cases,
        stock_repository=stock_repository,
        profile_repository=profile_repository,
        current_profile=current_profile,
        market_data_provider=market_data_provider,
        fundamental_data_provider=fundamental_data_provider,
        sec_filings_provider=sec_filings_provider,
        macro_data_provider=macro_data_provider,
        cache_manager=cache_manager,
        profile_management_service=profile_management_service,
        llm_config=llm_config,
        prompt_manager=prompt_manager,
    )
    get_instrument_use_case = providers.Callable(
        lambda config: config["get_instrument_use_case"](),
        config=_use_cases_config,
    )
    search_instruments_use_case = providers.Callable(
        lambda config: config["search_instruments_use_case"](),
        config=_use_cases_config,
    )
    get_quote_use_case = providers.Callable(
        lambda config: config["get_quote_use_case"](),
        config=_use_cases_config,
    )
    get_historical_data_use_case = providers.Callable(
        lambda config: config["get_historical_data_use_case"](),
        config=_use_cases_config,
    )
    get_options_chain_use_case = providers.Callable(
        lambda config: config["get_options_chain_use_case"](),
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
    get_stock_fundamentals_use_case = providers.Callable(
        lambda config: config["get_stock_fundamentals_use_case"](),
        config=_use_cases_config,
    )
    job_runner = providers.Callable(
        lambda config: config["job_runner"](),
        config=_use_cases_config,
    )
    # Runners for analyze (override these to use your own executors; default uses JobRunner)
    analyze_instrument_runner = providers.Factory(
        DefaultAnalyzeInstrumentRunner,
        job_runner=job_runner,
    )
    analyze_market_runner = providers.Factory(
        DefaultAnalyzeMarketRunner,
        job_runner=job_runner,
    )
    analyze_instrument_use_case = providers.Factory(
        AnalyzeInstrumentUseCase,
        analyze_instrument_runner=analyze_instrument_runner,
    )
    analyze_market_use_case = providers.Factory(
        AnalyzeMarketUseCase,
        analyze_market_runner=analyze_market_runner,
    )
    analysis_executors = providers.Callable(
        lambda config: config["analysis_executors"](),
        config=_use_cases_config,
    )


# Global container instance (can be overridden for testing)
_container: Container | None = None


def get_container(
    llm_config: LLMConfig | None = None,
    fred_api_key: str | None = None,
    load_from_env: bool = True,
    prompt_templates: dict[str, dict[str, str]] | None = None,
    prompt_manager: PromptManager | None = None,
    cache_enabled: bool | None = None,
    cache_manager: CacheManager | None = None,
) -> Container:
    """Get the global dependency injection container.

    Args:
        llm_config: Optional LLM configuration. If None and load_from_env is True,
                   will attempt to load from environment variables.
        fred_api_key: Optional FRED API key. If None, uses COPINANCEOS_FRED_API_KEY from
                     settings (for CLI users). Library integrators should pass their own
                     API key here.
        load_from_env: If True and llm_config is None, attempt to load LLM config
                      from environment variables (CLI convenience).
        prompt_templates: Optional overlay of prompt templates. Keys are prompt names
            (e.g. ``analyze_question_driven``), values are ``{"system_prompt": str, "user_prompt": str}``.
            Used for question-driven and other analysis executors; missing names fall back to built-in defaults.
            Ignored if ``prompt_manager`` is provided.
        prompt_manager: Optional custom PromptManager. If provided, used for all prompt
            resolution; ``prompt_templates`` is ignored. If neither this nor
            ``prompt_templates`` is provided, the default PromptManager (package prompts)
            is used.
        cache_enabled: If False, disable built-in cache (tool results and agent prompts).
            If None, uses settings (COPINANCEOS_CACHE_ENABLED, default True). Ignored if
            ``cache_manager`` is provided.
        cache_manager: Optional custom CacheManager. If provided, used for tool and
            prompt caching; ``cache_enabled`` is ignored. Pass your own implementation
            when using the library with your own caching layer. If you want no cache,
            pass ``cache_enabled=False`` instead.

    Returns:
        Container instance
    """
    global _container
    # For library integrators, always create a new container if fred_api_key is provided
    # (to allow different API keys per instance)
    if _container is None or fred_api_key is not None:
        container_instance = Container()

        # Load LLM config if not provided
        if llm_config is None and load_from_env:
            llm_config = load_llm_config_from_env()

        if llm_config is not None:
            container_instance.llm_config.override(llm_config)

        # Override FRED API key if provided (for library integrators)
        if fred_api_key is not None:
            container_instance.fred_api_key_config.override(fred_api_key)

        # Prompt templates: custom manager or overlay; otherwise default
        if prompt_manager is not None:
            container_instance.prompt_manager.override(providers.Object(prompt_manager))
        elif prompt_templates is not None:
            container_instance.prompt_manager.override(
                providers.Singleton(PromptManager, templates=prompt_templates)
            )

        # Cache: custom manager, or disable if cache_enabled=False
        if cache_manager is not None:
            container_instance.cache_manager.override(providers.Object(cache_manager))
        elif cache_enabled is False or (cache_enabled is None and not get_settings().cache_enabled):
            container_instance.cache_manager.override(providers.Object(None))

        if _container is None:
            _container = container_instance
        else:
            # Return new instance for library integrators with custom API key
            return container_instance
    # Apply cache overrides to existing container (library use: cache disable was ignored)
    if cache_manager is not None:
        _container.cache_manager.override(providers.Object(cache_manager))
    elif cache_enabled is False or (cache_enabled is None and not get_settings().cache_enabled):
        _container.cache_manager.override(providers.Object(None))
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


class _ContainerProxy:
    """Lazy proxy for the global container.

    Delegates to get_container() on every attribute access so that:
    - No container is created at import time (lazy initialization).
    - Library code that calls get_container(cache_enabled=False) first gets
      a container created with those options; later access via this proxy
      returns the same instance.
    - Explicit cache/LLM/FRED overrides passed to get_container() are applied
      when returning an existing container, so options are never ignored.

    Does not use __slots__ so that unittest.mock.patch() can set attributes
    on the proxy (e.g. @patch("...container.cache_manager")).
    """

    def __getattr__(self, name: str) -> object:
        return getattr(get_container(), name)


# Lazy default container: no creation at import; first use or get_container(...) wins
container: Container = _ContainerProxy()  # type: ignore[assignment]
