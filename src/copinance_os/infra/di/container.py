"""Main dependency injection container configuration.

This module composes all container modules into a single Container class.

### Import-cost design
Every heavy vendor library (openai, pandas, google-genai, edgar, yfinance, QuantLib …)
is imported *lazily* — either inside the ``configure_*`` factory functions (which are
only called when a provider is first resolved) or inside the thin factory helpers
defined below the class body (prefixed ``_make_``).  Importing this module itself is
cheap so that ``create_container()`` can be called by a lazy interface bootstrap without
adding startup latency.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dependency_injector import containers, providers

from copinance_os.infra.di.data_providers import configure_data_providers
from copinance_os.infra.di.profile_use_cases import configure_profile_use_cases
from copinance_os.infra.di.repositories import configure_repositories
from copinance_os.infra.di.services import configure_services
from copinance_os.infra.di.storage import configure_storage
from copinance_os.infra.di.use_cases import configure_use_cases

if TYPE_CHECKING:
    from copinance_os.ai.llm.config import LLMConfig
    from copinance_os.ai.llm.resources import PromptManager
    from copinance_os.data.cache import CacheManager


# ---------------------------------------------------------------------------
# Thin factory helpers — deferred imports so Container class body stays light
# ---------------------------------------------------------------------------


def _make_prompt_manager() -> Any:
    from copinance_os.ai.llm.resources import PromptManager  # noqa: PLC0415

    return PromptManager()


def _make_null_cache_manager() -> Any:
    from copinance_os.data.cache import CacheManager  # noqa: PLC0415

    return CacheManager()


def _make_prompt_manager_with_templates(templates: dict[str, dict[str, str]]) -> Any:
    from copinance_os.ai.llm.resources import PromptManager  # noqa: PLC0415

    return PromptManager(templates=templates)


def _make_analyze_instrument_runner(research_orchestrator: Any) -> Any:
    from copinance_os.core.orchestrator.runners import (  # noqa: PLC0415
        DefaultAnalyzeInstrumentRunner,
    )

    return DefaultAnalyzeInstrumentRunner(research_orchestrator=research_orchestrator)


def _make_analyze_market_runner(research_orchestrator: Any) -> Any:
    from copinance_os.core.orchestrator.runners import (  # noqa: PLC0415
        DefaultAnalyzeMarketRunner,
    )

    return DefaultAnalyzeMarketRunner(research_orchestrator=research_orchestrator)


def _make_analyze_instrument_use_case(analyze_instrument_runner: Any) -> Any:
    from copinance_os.research.workflows.analyze import (  # noqa: PLC0415
        AnalyzeInstrumentUseCase,
    )

    return AnalyzeInstrumentUseCase(analyze_instrument_runner=analyze_instrument_runner)


def _make_analyze_market_use_case(analyze_market_runner: Any) -> Any:
    from copinance_os.research.workflows.analyze import (  # noqa: PLC0415
        AnalyzeMarketUseCase,
    )

    return AnalyzeMarketUseCase(analyze_market_runner=analyze_market_runner)


# ---------------------------------------------------------------------------
# Container
# ---------------------------------------------------------------------------


class Container(containers.DeclarativeContainer):
    """Dependency injection container for Copinance OS.

    This container composes providers from modular configuration modules:
    - Storage backend
    - Repositories
    - Domain services
    - Data providers
    - Use cases

    To use LLM features, provide llm_config when creating the container:
        from copinance_os.ai.llm.config import LLMConfig
        from copinance_os.infra.di import create_container

        llm_config = LLMConfig(
            provider="gemini",
            api_key="your-api-key",
            model="gemini-1.5-pro"
        )
        container = create_container(llm_config=llm_config)

    To provide your own FRED API key (for library integrators):
        container = create_container(fred_api_key="your-fred-api-key")

    Or override after creation:
        container = Container()
        container.llm_config.override(llm_config)
        container.fred_api_key_config.override("your-fred-api-key")
    """

    # Configuration
    config = providers.Configuration()
    llm_config = providers.Configuration()
    fred_api_key_config = providers.Configuration()

    # Prompt templates: default manager (package prompts). Override via create_container().
    # Uses _make_prompt_manager so PromptManager is only imported when first resolved.
    prompt_manager = providers.Singleton(_make_prompt_manager)

    # Storage backend (singleton, configured from settings)
    storage_backend = configure_storage()

    # Repositories (singletons, use shared storage backend)
    _repositories_config = configure_repositories(storage_backend)
    stock_repository = _repositories_config["stock_repository"]
    profile_repository = _repositories_config["profile_repository"]
    current_profile = _repositories_config["current_profile"]

    # Domain services
    _services_config = configure_services(profile_repository)
    profile_management_service = _services_config["profile_management_service"]

    # Side-effect-free cache default. Persistent and memory caches are explicit
    # composition choices made by create_container().
    cache_manager = providers.Singleton(_make_null_cache_manager)

    # Data providers (singletons, can be overridden).
    # Singleton caches the provider dict so inner Singletons (yfinance, cache, …) are not
    # rebuilt on every use-case resolution.  configure_data_providers itself is only
    # invoked when the Singleton is first resolved (not at class-definition time).
    _data_providers_config = providers.Singleton(
        configure_data_providers,
        llm_config=llm_config,
        cache_manager=cache_manager,
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
    llm_analyzer = providers.Callable(
        lambda config: config["llm_analyzer"](),
        config=_data_providers_config,
    )
    llm_analyzer_for_analysis = providers.Callable(
        lambda config: config["llm_analyzer_for_analysis"](),
        config=_data_providers_config,
    )

    # Profile use cases: resolved without market/fundamentals/cache graph.
    _profile_use_cases_config = providers.Singleton(
        configure_profile_use_cases,
        profile_repository=profile_repository,
        current_profile=current_profile,
        profile_management_service=profile_management_service,
    )

    # Market / research / analysis use cases (pulls full provider graph when first used).
    _use_cases_config = providers.Singleton(
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
        config=_profile_use_cases_config,
    )
    get_current_profile_use_case = providers.Callable(
        lambda config: config["get_current_profile_use_case"](),
        config=_profile_use_cases_config,
    )
    set_current_profile_use_case = providers.Callable(
        lambda config: config["set_current_profile_use_case"](),
        config=_profile_use_cases_config,
    )
    delete_profile_use_case = providers.Callable(
        lambda config: config["delete_profile_use_case"](),
        config=_profile_use_cases_config,
    )
    get_profile_use_case = providers.Callable(
        lambda config: config["get_profile_use_case"](),
        config=_profile_use_cases_config,
    )
    list_profiles_use_case = providers.Callable(
        lambda config: config["list_profiles_use_case"](),
        config=_profile_use_cases_config,
    )
    get_stock_fundamentals_use_case = providers.Callable(
        lambda config: config["get_stock_fundamentals_use_case"](),
        config=_use_cases_config,
    )
    research_orchestrator = providers.Callable(
        lambda config: config["research_orchestrator"](),
        config=_use_cases_config,
    )
    # Analyze runners — _make_* helpers defer the heavy runner/use-case imports
    analyze_instrument_runner = providers.Factory(
        _make_analyze_instrument_runner,
        research_orchestrator=research_orchestrator,
    )
    analyze_market_runner = providers.Factory(
        _make_analyze_market_runner,
        research_orchestrator=research_orchestrator,
    )
    analyze_instrument_use_case = providers.Factory(
        _make_analyze_instrument_use_case,
        analyze_instrument_runner=analyze_instrument_runner,
    )
    analyze_market_use_case = providers.Factory(
        _make_analyze_market_use_case,
        analyze_market_runner=analyze_market_runner,
    )
    analysis_executors = providers.Callable(
        lambda config: config["analysis_executors"](),
        config=_use_cases_config,
    )
    generate_market_narrative_use_case = providers.Callable(
        lambda config: config["generate_market_narrative_use_case"](),
        config=_use_cases_config,
    )
    generate_curated_questions_use_case = providers.Callable(
        lambda config: config["generate_curated_questions_use_case"](),
        config=_use_cases_config,
    )


def create_container(
    llm_config: LLMConfig | None = None,
    fred_api_key: str | None = None,
    load_from_env: bool = False,
    prompt_templates: dict[str, dict[str, str]] | None = None,
    prompt_manager: PromptManager | None = None,
    cache_manager: CacheManager | None = None,
    storage_type: str = "memory",
    storage_path: str | None = None,
    storage_backend: Any | None = None,
    current_profile_path: str | None = None,
    market_data_provider: Any | None = None,
    fundamental_data_provider: Any | None = None,
    sec_filings_provider: Any | None = None,
    macro_data_provider: Any | None = None,
) -> Container:
    """Create an independent, library-safe dependency injection container.

    Defaults are deliberately side-effect free: memory repositories, memory
    profile state, a no-op cache, and no environment-based LLM configuration.
    File persistence and caching require explicit backends/paths.

    Args:
        llm_config: Optional LLM configuration. If None and load_from_env is True,
                   will attempt to load from environment variables.
        fred_api_key: Optional FRED API key. If None, uses COPINANCEOS_FRED_API_KEY from
                     settings (for CLI users). Library integrators should pass their own
                     API key here.
        load_from_env: Explicitly opt into environment-based LLM configuration.
        prompt_templates: Optional overlay of prompt templates. Keys are prompt names
            (e.g. ``analyze_question_driven``), values are ``{"system_prompt": str, "user_prompt": str}``.
            Used for question-driven and other analysis executors; missing names fall back to built-in defaults.
            Ignored if ``prompt_manager`` is provided.
        prompt_manager: Optional custom PromptManager. If provided, used for all prompt
            resolution; ``prompt_templates`` is ignored. If neither this nor
            ``prompt_templates`` is provided, the default PromptManager (package prompts)
            is used.
        cache_manager: Explicit cache manager. Omit for a no-op cache.
        storage_type: ``"memory"`` (default) or ``"file"``.
        storage_path: Required when ``storage_type="file"``.
        storage_backend: Optional pre-built ``Storage`` instance. When provided,
            takes precedence over ``storage_type`` and ``storage_path``. Use this
            when you have a custom ``Storage`` implementation (e.g. SQLite, S3) and
            want to inject it directly. For Postgres, prefer overriding individual
            repository providers via ``container.stock_repository.override()`` after
            this container, since the ``Storage`` ABC is oriented toward collection-based
            backends (file/memory); a Postgres backend is better expressed as async
            repository implementations.
        market_data_provider: Optional host-owned market-data provider.
        fundamental_data_provider: Optional host-owned fundamentals provider.
        sec_filings_provider: Optional host-owned SEC filings provider.
        macro_data_provider: Optional host-owned macro-data provider.

    Returns:
        Container instance
    """
    container_instance = Container()

    if llm_config is None and load_from_env:
        from copinance_os.ai.llm.config_loader import load_llm_config_from_env  # noqa: PLC0415

        llm_config = load_llm_config_from_env()
    if llm_config is not None:
        container_instance.llm_config.override(llm_config)
    if fred_api_key is not None:
        container_instance.fred_api_key_config.override(fred_api_key)

    if prompt_manager is not None:
        container_instance.prompt_manager.override(providers.Object(prompt_manager))
    elif prompt_templates is not None:
        container_instance.prompt_manager.override(
            providers.Singleton(_make_prompt_manager_with_templates, templates=prompt_templates)
        )

    if cache_manager is not None:
        container_instance.cache_manager.override(providers.Object(cache_manager))

    if storage_backend is not None:
        container_instance.storage_backend.override(providers.Object(storage_backend))
    else:
        from copinance_os.data.repositories.storage import create_storage  # noqa: PLC0415

        if storage_type == "file" and storage_path is None:
            raise ValueError("storage_path is required when storage_type='file'")
        storage = create_storage(storage_type=storage_type, base_path=storage_path)
        container_instance.storage_backend.override(providers.Object(storage))

    if current_profile_path is not None:
        from copinance_os.data.repositories.profile import CurrentProfile  # noqa: PLC0415

        container_instance.current_profile.override(
            providers.Singleton(CurrentProfile, config_path=current_profile_path)
        )

    provider_overrides = (
        (container_instance.market_data_provider, market_data_provider),
        (container_instance.fundamental_data_provider, fundamental_data_provider),
        (container_instance.sec_filings_provider, sec_filings_provider),
        (container_instance.macro_data_provider, macro_data_provider),
    )
    for provider, override in provider_overrides:
        if override is not None:
            provider.override(providers.Object(override))

    return container_instance
