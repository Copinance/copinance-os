"""Factory for creating analysis executors."""

import structlog

from copinanceos.application.use_cases.fundamentals import GetStockFundamentalsUseCase
from copinanceos.application.use_cases.market import (
    GetHistoricalDataUseCase,
    GetInstrumentUseCase,
    GetOptionsChainUseCase,
    GetQuoteUseCase,
)
from copinanceos.domain.ports.analysis_execution import AnalysisExecutor
from copinanceos.domain.ports.data_providers import (
    FundamentalDataProvider,
    MacroeconomicDataProvider,
    MarketDataProvider,
)
from copinanceos.infrastructure.analyzers.llm.config import LLMConfig
from copinanceos.infrastructure.analyzers.llm.providers.factory import LLMProviderFactory
from copinanceos.infrastructure.analyzers.llm.resources import PromptManager
from copinanceos.infrastructure.cache import CacheManager
from copinanceos.infrastructure.executors import (
    InstrumentAnalysisExecutor,
    MarketAnalysisExecutor,
    QuestionDrivenAnalysisExecutor,
)
from copinanceos.infrastructure.factories.llm_analyzer import LLMAnalyzerFactory

logger = structlog.get_logger(__name__)


class AnalysisExecutorFactory:
    """Factory for creating analysis executor instances."""

    @staticmethod
    def create_all(
        get_instrument_use_case: GetInstrumentUseCase,
        get_quote_use_case: GetQuoteUseCase,
        get_historical_data_use_case: GetHistoricalDataUseCase,
        get_options_chain_use_case: GetOptionsChainUseCase,
        market_data_provider: MarketDataProvider,
        macro_data_provider: MacroeconomicDataProvider,
        fundamentals_use_case: GetStockFundamentalsUseCase,
        fundamental_data_provider: FundamentalDataProvider,
        sec_filings_provider: FundamentalDataProvider,
        cache_manager: CacheManager | None,
        llm_config: LLMConfig | None = None,
        prompt_manager: PromptManager | None = None,
    ) -> list[AnalysisExecutor]:
        """Create all available analysis executors with their dependencies."""
        executors: list[AnalysisExecutor] = [
            InstrumentAnalysisExecutor(
                get_instrument_use_case=get_instrument_use_case,
                get_quote_use_case=get_quote_use_case,
                get_historical_data_use_case=get_historical_data_use_case,
                get_options_chain_use_case=get_options_chain_use_case,
                fundamentals_use_case=fundamentals_use_case,
                cache_manager=cache_manager,
            ),
            MarketAnalysisExecutor(
                market_data_provider=market_data_provider,
                macro_data_provider=macro_data_provider,
                cache_manager=cache_manager,
            ),
        ]

        agent_added = False
        if llm_config:
            try:
                provider_name = LLMProviderFactory.get_provider_for_execution_type(
                    "question_driven_analysis", llm_config=llm_config
                )
                llm_analyzer = LLMAnalyzerFactory.create(provider_name, llm_config=llm_config)

                try:
                    provider = llm_analyzer._llm_provider  # type: ignore[attr-defined]
                    if hasattr(provider, "_api_key") and provider._api_key is None:
                        logger.warning(
                            "LLM provider API key not configured",
                            provider=provider.get_provider_name(),
                            hint="Provide API key in LLMConfig",
                        )
                    else:
                        executors.append(
                            QuestionDrivenAnalysisExecutor(
                                llm_analyzer=llm_analyzer,
                                market_data_provider=market_data_provider,
                                macro_data_provider=macro_data_provider,
                                fundamental_data_provider=fundamental_data_provider,
                                sec_filings_provider=sec_filings_provider,
                                cache_manager=cache_manager,
                                prompt_manager=prompt_manager,
                            )
                        )
                        agent_added = True
                except Exception as e:
                    logger.warning(
                        "Failed to initialize LLM analyzer for question-driven analysis",
                        error=str(e),
                        hint="Check LLM configuration",
                    )
            except Exception as e:
                logger.warning(
                    "Failed to create LLM analyzer for question-driven analysis",
                    error=str(e),
                    hint="Check LLM configuration",
                )
        else:
            logger.debug("LLM config not provided, using fallback question-driven executor")

        if not agent_added:
            executors.append(
                QuestionDrivenAnalysisExecutor(
                    llm_analyzer=None,
                    market_data_provider=market_data_provider,
                    macro_data_provider=macro_data_provider,
                    fundamental_data_provider=fundamental_data_provider,
                    sec_filings_provider=sec_filings_provider,
                    cache_manager=cache_manager,
                    prompt_manager=prompt_manager,
                )
            )

        return executors
