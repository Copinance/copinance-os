"""Market / analysis use case configuration.

Heavy dependencies (openai, pandas, edgar, QuantLib, google-genai …) are imported
*inside* ``configure_use_cases`` so that importing this module is nearly free.  The
function is only called when the ``providers.Singleton`` wrapping it is first resolved
— i.e. when an actual market or analysis command runs, not at CLI startup.

Profile use cases live in ``infra.di.profile_use_cases`` (no heavy deps).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
    from copinance_os.ai.curated_questions.generator import (  # noqa: PLC0415
        CuratedQuestionsGenerator,
    )
    from copinance_os.core.execution_engine.factory import AnalysisExecutorFactory  # noqa: PLC0415
    from copinance_os.core.orchestrator.research_orchestrator import (  # noqa: PLC0415
        ResearchOrchestrator,
    )
    from copinance_os.core.orchestrator.run_job import DefaultJobRunner  # noqa: PLC0415
    from copinance_os.core.pipeline.tools.discovery.allowlist import (  # noqa: PLC0415
        question_driven_tool_names,
    )
    from copinance_os.research.workflows.curated_questions import (  # noqa: PLC0415
        GenerateCuratedQuestionsUseCase,
    )
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
    from copinance_os.research.workflows.narrative import (  # noqa: PLC0415
        GenerateMarketNarrativeUseCase,
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

    # Narrative use case — needs the analyze_market_runner and, when available, an LLM provider.
    # The LLM provider is resolved lazily inside the factory so LLM SDKs only load if configured.
    def _make_analyze_market_runner_for_narrative() -> Any:
        from copinance_os.core.orchestrator.runners import (  # noqa: PLC0415
            DefaultAnalyzeMarketRunner,
        )

        return DefaultAnalyzeMarketRunner(research_orchestrator=research_orchestrator())

    def _make_llm_provider_optional() -> Any:
        if llm_config is None:
            return None
        try:
            from copinance_os.ai.llm.providers.factory import LLMProviderFactory  # noqa: PLC0415

            provider_name = LLMProviderFactory.get_provider_for_execution_type(
                "question_driven_analysis", llm_config=llm_config
            )
            from copinance_os.ai.llm.analyzer_factory import LLMAnalyzerFactory  # noqa: PLC0415

            analyzer = LLMAnalyzerFactory.create(provider_name, llm_config=llm_config)
            return getattr(analyzer, "_llm_provider", None)
        except Exception:
            return None

    _llm_provider_optional = providers.Callable(_make_llm_provider_optional)

    curated_questions_generator = providers.Factory(
        CuratedQuestionsGenerator,
        allowed_tool_names=providers.Callable(question_driven_tool_names),
        prompt_manager=prompt_manager,
    )

    generate_curated_questions_use_case = providers.Factory(
        GenerateCuratedQuestionsUseCase,
        generator=curated_questions_generator,
        cache_manager=cache_manager,
        llm_provider=_llm_provider_optional,
    )

    generate_market_narrative_use_case = providers.Factory(
        GenerateMarketNarrativeUseCase,
        analyze_market_runner=providers.Callable(_make_analyze_market_runner_for_narrative),
        llm_provider=_llm_provider_optional,
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
        "generate_market_narrative_use_case": generate_market_narrative_use_case,
        "generate_curated_questions_use_case": generate_curated_questions_use_case,
    }
