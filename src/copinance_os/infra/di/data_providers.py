"""Data provider container configuration.

Heavy provider imports (yfinance, QuantLib, edgartools, FRED, openai, google-genai …)
live *inside* ``configure_data_providers`` so that importing this module is nearly
free.  The function is only invoked when the ``providers.Singleton`` wrapping it is
first resolved at runtime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from dependency_injector import providers

if TYPE_CHECKING:
    from copinance_os.ai.llm.config import LLMConfig


def configure_data_providers(
    llm_config: LLMConfig | None = None,
    fred_api_key: str | None = None,
) -> dict[str, providers.Provider]:
    """Configure data provider providers.

    All heavy imports (yfinance, QuantLib, edgartools, FRED client, LLM SDKs) are
    deferred to this function body so importing the module has no measurable cost.

    Args:
        llm_config: Optional LLM configuration. If None, LLM analyzers will use defaults.
        fred_api_key: Optional FRED API key. If None, uses COPINANCEOS_FRED_API_KEY from settings.

    Returns:
        Dictionary of data provider providers
    """
    import os  # noqa: PLC0415
    from datetime import timedelta  # noqa: PLC0415

    from copinance_os.ai.llm.analyzer_factory import LLMAnalyzerFactory  # noqa: PLC0415
    from copinance_os.data.analytics.options import (  # noqa: PLC0415
        QuantLibBsmGreekEstimator,
    )
    from copinance_os.data.cache import CacheManager, LocalFileCacheBackend  # noqa: PLC0415
    from copinance_os.data.providers import (  # noqa: PLC0415
        EdgarToolsFundamentalProvider,
        FredMacroeconomicProvider,
        YFinanceFundamentalProvider,
        YFinanceMarketProvider,
    )
    from copinance_os.data.providers.market import (  # noqa: PLC0415
        OptionAnalyticsMarketDataProvider,
    )
    from copinance_os.infra.config import get_settings  # noqa: PLC0415

    settings = get_settings()
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
            provider_name=None,
            llm_config=llm_config,
        ),
        "llm_analyzer_for_analysis": providers.Factory(
            LLMAnalyzerFactory.create_for_execution_type,
            execution_type="question_driven_analysis",
            llm_config=llm_config,
        ),
    }
