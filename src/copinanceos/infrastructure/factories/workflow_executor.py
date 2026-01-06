"""Factory for creating workflow executors."""

import structlog

from copinanceos.application.use_cases.fundamentals import ResearchStockFundamentalsUseCase
from copinanceos.application.use_cases.stock import GetStockUseCase
from copinanceos.domain.ports.data_providers import (
    FundamentalDataProvider,
    MacroeconomicDataProvider,
    MarketDataProvider,
)
from copinanceos.domain.ports.workflows import WorkflowExecutor
from copinanceos.infrastructure.analyzers.llm.config import LLMConfig
from copinanceos.infrastructure.analyzers.llm.providers.factory import LLMProviderFactory
from copinanceos.infrastructure.cache import CacheManager
from copinanceos.infrastructure.factories.llm_analyzer import LLMAnalyzerFactory
from copinanceos.infrastructure.workflows import (
    AgenticWorkflowExecutor,
    MacroRegimeStaticWorkflowExecutor,
    StaticWorkflowExecutor,
)

logger = structlog.get_logger(__name__)


class WorkflowExecutorFactory:
    """Factory for creating workflow executor instances."""

    @staticmethod
    def create_all(
        get_stock_use_case: GetStockUseCase,
        market_data_provider: MarketDataProvider,
        macro_data_provider: MacroeconomicDataProvider,
        fundamentals_use_case: ResearchStockFundamentalsUseCase,
        fundamental_data_provider: FundamentalDataProvider,
        sec_filings_provider: FundamentalDataProvider,
        cache_manager: CacheManager,
        llm_config: LLMConfig | None = None,
    ) -> list[WorkflowExecutor]:
        """Create all available workflow executors with their dependencies.

        Args:
            get_stock_use_case: Use case for getting stock information
            market_data_provider: Provider for market data
            fundamentals_use_case: Use case for researching stock fundamentals
            fundamental_data_provider: Provider for fundamental data
            sec_filings_provider: Provider for SEC filings
            cache_manager: Cache manager for tool caching
            llm_config: LLM configuration. If None, agent workflows will not be available.

        Returns:
            List of workflow executors
        """
        executors: list[WorkflowExecutor] = [
            StaticWorkflowExecutor(
                get_stock_use_case=get_stock_use_case,
                market_data_provider=market_data_provider,
                fundamentals_use_case=fundamentals_use_case,
            ),
            MacroRegimeStaticWorkflowExecutor(
                market_data_provider=market_data_provider,
                macro_data_provider=macro_data_provider,
            ),
        ]

        # Add agent executor if LLM config is provided
        if llm_config:
            try:
                # Get LLM analyzer for agent workflow
                provider_name = LLMProviderFactory.get_provider_for_workflow(
                    "agent", llm_config=llm_config
                )
                llm_analyzer = LLMAnalyzerFactory.create(provider_name, llm_config=llm_config)

                # Verify the analyzer has a provider with API key configured (for cloud providers)
                try:
                    provider = llm_analyzer._llm_provider  # type: ignore[attr-defined]
                    # Check if provider has API key (for Gemini, OpenAI, Anthropic)
                    if hasattr(provider, "_api_key") and provider._api_key is None:
                        logger.warning(
                            "LLM provider API key not configured",
                            provider=provider.get_provider_name(),
                            hint="Provide API key in LLMConfig",
                        )
                    else:
                        executors.append(
                            AgenticWorkflowExecutor(
                                llm_analyzer=llm_analyzer,
                                market_data_provider=market_data_provider,
                                macro_data_provider=macro_data_provider,
                                fundamental_data_provider=fundamental_data_provider,
                                sec_filings_provider=sec_filings_provider,
                                cache_manager=cache_manager,
                            )
                        )
                except Exception as e:
                    logger.warning(
                        "Failed to initialize LLM analyzer for agent workflow",
                        error=str(e),
                        hint="Check LLM configuration",
                    )
            except Exception as e:
                logger.warning(
                    "Failed to create LLM analyzer for agent workflow",
                    error=str(e),
                    hint="Check LLM configuration",
                )
        else:
            logger.debug("LLM config not provided, skipping agent workflow executor")

        return executors
