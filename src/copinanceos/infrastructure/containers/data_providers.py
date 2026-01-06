"""Data provider container configuration."""

from datetime import timedelta

from dependency_injector import providers

from copinanceos.infrastructure.analyzers.llm.config import LLMConfig
from copinanceos.infrastructure.cache import CacheManager, LocalFileCacheBackend
from copinanceos.infrastructure.config import get_settings
from copinanceos.infrastructure.data_providers import (
    EdgarFundamentalProvider,
    FredMacroeconomicProvider,
    YFinanceFundamentalProvider,
    YFinanceMarketProvider,
)
from copinanceos.infrastructure.factories import LLMAnalyzerFactory


def configure_data_providers(
    llm_config: LLMConfig | None = None,
    fred_api_key: str | None = None,
) -> dict[str, providers.Provider]:
    """Configure data provider providers.

    Args:
        llm_config: Optional LLM configuration. If None, LLM analyzers will use defaults.
        fred_api_key: Optional FRED API key. If None, uses COPINANCEOS_FRED_API_KEY from settings
                     (for CLI users). Library integrators should pass their own API key here.

    Returns:
        Dictionary of data provider providers
    """
    settings = get_settings()
    # Use provided API key if given, otherwise fall back to settings (CLI default)
    effective_fred_api_key = fred_api_key if fred_api_key is not None else settings.fred_api_key

    return {
        "market_data_provider": providers.Singleton(YFinanceMarketProvider),
        "fundamental_data_provider": providers.Singleton(YFinanceFundamentalProvider),
        "sec_filings_provider": providers.Singleton(EdgarFundamentalProvider),
        "macro_data_provider": providers.Singleton(
            FredMacroeconomicProvider,
            api_key=effective_fred_api_key,
            base_url=settings.fred_base_url,
            rate_limit_delay=settings.fred_rate_limit_delay,
            timeout_seconds=settings.fred_timeout_seconds,
        ),
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
            workflow_type="agent",  # Default workflow type
            llm_config=llm_config,
        ),
    }
