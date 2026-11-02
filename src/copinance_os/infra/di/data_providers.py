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
    cache_manager: object | None = None,
    standalone: bool = False,
) -> dict[str, providers.Provider]:
    """Configure data provider providers.

    In pure engine mode (default for library callers), null fail-closed providers are
    wired, preventing any un-governed scraping or network calls. Host apps inject
    facts via ``FactBasedMarketProvider`` or ``market_data_provider``. Standalone CLI
    commands pass ``standalone=True`` to wire vendor adapters.

    Args:
        llm_config: Optional LLM configuration. If None, LLM analyzers will use defaults.
        fred_api_key: Optional FRED API key. If None, uses COPINANCEOS_FRED_API_KEY from settings.
        cache_manager: Optional cache manager.
        standalone: Whether to wire vendor network providers. Callers must resolve this
            (including any ``COPINANCE_STANDALONE`` env fallback) before calling — this
            function trusts the value it is given rather than re-reading the environment,
            so there is exactly one place that decides engine-vs-standalone mode.

    Returns:
        Dictionary of data provider providers
    """
    from copinance_os.ai.llm.analyzer_factory import LLMAnalyzerFactory  # noqa: PLC0415

    if not standalone:
        from copinance_os.data.providers.facts import (  # noqa: PLC0415
            NullFundamentalDataProvider,
            NullMacroDataProvider,
            NullMarketDataProvider,
        )

        return {
            "market_data_provider": providers.Singleton(NullMarketDataProvider),
            "fundamental_data_provider": providers.Singleton(NullFundamentalDataProvider),
            "sec_filings_provider": providers.Singleton(NullFundamentalDataProvider),
            "macro_data_provider": providers.Singleton(NullMacroDataProvider),
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

    import os  # noqa: PLC0415

    from copinance_os.data.analytics.options import (  # noqa: PLC0415
        QuantLibBsmGreekEstimator,
    )
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
