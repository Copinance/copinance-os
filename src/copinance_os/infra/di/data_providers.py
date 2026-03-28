"""Data provider container configuration."""

import os
from datetime import timedelta

from dependency_injector import providers

from copinance_os.ai.llm.config import LLMConfig
from copinance_os.data.analytics.options import QuantLibBsmGreekEstimator
from copinance_os.data.cache import CacheManager, LocalFileCacheBackend
from copinance_os.data.providers import (
    EdgarToolsFundamentalProvider,
    FredMacroeconomicProvider,
    YFinanceFundamentalProvider,
    YFinanceMarketProvider,
)
from copinance_os.data.providers.market import OptionAnalyticsMarketDataProvider
from copinance_os.infra.config import get_settings
from copinance_os.infra.factories import LLMAnalyzerFactory


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

    yfinance_market_provider = providers.Singleton(YFinanceMarketProvider)
    option_greeks_estimator = providers.Singleton(QuantLibBsmGreekEstimator)
    # Prefer EDGAR_IDENTITY (edgartools convention); else settings default / COPINANCEOS_EDGAR_IDENTITY
    edgar_identity = os.environ.get("EDGAR_IDENTITY") or settings.edgar_identity

    cache_manager = providers.Singleton(
        CacheManager,
        backend=providers.Singleton(LocalFileCacheBackend),
        default_ttl=timedelta(hours=1),
    )

    return {
        "market_data_provider": providers.Singleton(
            OptionAnalyticsMarketDataProvider,
            inner=yfinance_market_provider,
            option_greeks_estimator=option_greeks_estimator,
        ),
        "fundamental_data_provider": providers.Singleton(YFinanceFundamentalProvider),
        "sec_filings_provider": providers.Singleton(
            EdgarToolsFundamentalProvider,
            identity=edgar_identity,
            cache_manager=cache_manager,
        ),
        "macro_data_provider": providers.Singleton(
            FredMacroeconomicProvider,
            api_key=effective_fred_api_key,
            base_url=settings.fred_base_url,
            rate_limit_delay=settings.fred_rate_limit_delay,
            timeout_seconds=settings.fred_timeout_seconds,
        ),
        "cache_manager": cache_manager,
        "llm_analyzer": providers.Factory(
            LLMAnalyzerFactory.create,
            provider_name=None,  # Will use default from llm_config if provided
            llm_config=llm_config,
        ),
        "llm_analyzer_for_analysis": providers.Factory(
            LLMAnalyzerFactory.create_for_execution_type,
            execution_type="question_driven_analysis",
            llm_config=llm_config,
        ),
    }
