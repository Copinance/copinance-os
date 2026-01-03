"""Data provider container configuration."""

from datetime import timedelta

from dependency_injector import providers

from copinanceos.infrastructure.analyzers.llm.config import LLMConfig
from copinanceos.infrastructure.cache import CacheManager, LocalFileCacheBackend
from copinanceos.infrastructure.data_providers import (
    EdgarFundamentalProvider,
    YFinanceFundamentalProvider,
    YFinanceMarketProvider,
)
from copinanceos.infrastructure.factories import LLMAnalyzerFactory


def configure_data_providers(
    llm_config: LLMConfig | None = None,
) -> dict[str, providers.Provider]:
    """Configure data provider providers.

    Args:
        llm_config: Optional LLM configuration. If None, LLM analyzers will use defaults.

    Returns:
        Dictionary of data provider providers
    """
    return {
        "market_data_provider": providers.Singleton(YFinanceMarketProvider),
        "fundamental_data_provider": providers.Singleton(YFinanceFundamentalProvider),
        "sec_filings_provider": providers.Singleton(EdgarFundamentalProvider),
        "cache_manager": providers.Singleton(
            CacheManager,
            backend=providers.Singleton(LocalFileCacheBackend),
            default_ttl=timedelta(hours=1),
        ),
        "llm_analyzer": providers.Factory(
            LLMAnalyzerFactory.create,
            provider_name=None,  # Will use default from llm_config if provided
            llm_config=llm_config,
        ),
        "llm_analyzer_for_workflow": providers.Factory(
            LLMAnalyzerFactory.create_for_workflow,
            workflow_type="static",  # Default workflow type
            llm_config=llm_config,
        ),
    }
