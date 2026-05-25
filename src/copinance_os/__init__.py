"""
Copinance OS - Open-source market analysis library and CLI.

A Python library (and standalone CLI) for short/mid/long-term market analysis with
deterministic pipelines and question-driven AI analysis.

Instrument analysis example::

    from copinance_os import AnalyzeInstrumentRequest, FinancialLiteracy
    from copinance_os.infra.di import get_container

    container = get_container()
    result = await container.analyze_instrument_runner().run(
        AnalyzeInstrumentRequest(
            symbol="AAPL",
            question="What is the current options positioning?",
            financial_literacy=FinancialLiteracy.INTERMEDIATE,
        )
    )

Market narrative (LLM prose summary) example::

    from copinance_os import MarketNarrativeRequest, FinancialLiteracy
    from copinance_os.ai.llm.config import LLMConfig
    from copinance_os.infra.di import get_container

    container = get_container(llm_config=LLMConfig(provider="openai", api_key="sk-..."))
    result = await container.generate_market_narrative_use_case().execute(
        MarketNarrativeRequest(
            market_index="SPY",
            financial_literacy=FinancialLiteracy.BEGINNER,
        )
    )
    print(result.narrative)   # result.fallback=True when LLM is unavailable

Curated follow-up questions (BFF chips; call after data fetch)::

    from copinance_os import (
        ArtifactType,
        GenerateCuratedQuestionsRequest,
        FinancialLiteracy,
    )
    from copinance_os.ai.llm.config import LLMConfig
    from copinance_os.infra.di import get_container

    container = get_container(llm_config=LLMConfig(provider="openai", api_key="sk-..."))
    quote_resp = await container.get_quote_use_case().execute(...)
    payload = {**quote_resp.quote, "symbol": quote_resp.symbol}
    block = await container.generate_curated_questions_use_case().execute(
        GenerateCuratedQuestionsRequest(
            artifact=ArtifactType.QUOTE,
            payload=payload,
            count=5,
            financial_literacy=FinancialLiteracy.BEGINNER,
        ),
        llm_provider_override=user_provider,  # optional per-user API key
    )
    # block.questions — LLM text; block.meta.llm_unavailable_reason when empty

Custom persistence backend (Postgres) example::

    from copinance_os import StockRepository
    from copinance_os.infra.di import get_container
    from dependency_injector import providers

    class PostgresStockRepository(StockRepository):
        ...  # implement async methods against your DB pool

    container = get_container()
    container.stock_repository.override(providers.Object(PostgresStockRepository(pool=pg_pool)))

Custom file-like storage backend::

    from copinance_os import Storage
    from copinance_os.infra.di import get_container

    class S3Storage(Storage):
        ...  # implement get_collection / save / clear

    container = get_container(storage_backend=S3Storage(bucket="my-bucket"))
"""

__version__ = "0.1.0"

# Re-export the most common types for library consumers so they have a single
# stable import path that won't change as internal modules are reorganised.
from copinance_os.data.analytics.options.positioning.bias import (  # noqa: E402
    signal_agreement_direction,
)
from copinance_os.data.analytics.options.positioning.iv_rank import iv_percentile_rank  # noqa: E402
from copinance_os.domain.models.analysis import (  # noqa: E402
    AnalyzeInstrumentRequest,
    AnalyzeMarketRequest,
    AnalyzeMode,
)
from copinance_os.domain.models.analysis_report import AnalysisReport  # noqa: E402
from copinance_os.domain.models.curated_questions import (  # noqa: E402
    ArtifactType,
    CuratedQuestion,
    CuratedQuestionsBlock,
    CuratedQuestionsMeta,
    GenerateCuratedQuestionsRequest,
    LLMUnavailableReason,
)
from copinance_os.domain.models.job import RunJobResult  # noqa: E402
from copinance_os.domain.models.narrative import (
    MarketNarrativeRequest,
    NarrativeResult,
)  # noqa: E402
from copinance_os.domain.models.profile import AnalysisProfile, FinancialLiteracy  # noqa: E402
from copinance_os.domain.models.regime import regime_confidence_score  # noqa: E402
from copinance_os.domain.ports.repositories import (  # noqa: E402
    AnalysisProfileRepository,
    StockRepository,
)
from copinance_os.domain.ports.storage import CacheBackend, Storage  # noqa: E402

__all__ = [
    "__version__",
    # Analysis request/response types
    "AnalyzeInstrumentRequest",
    "AnalyzeMarketRequest",
    "AnalyzeMode",
    "RunJobResult",
    "AnalysisReport",
    # Narrative request/response types
    "MarketNarrativeRequest",
    "NarrativeResult",
    # Curated questions
    "ArtifactType",
    "CuratedQuestion",
    "CuratedQuestionsBlock",
    "CuratedQuestionsMeta",
    "GenerateCuratedQuestionsRequest",
    "LLMUnavailableReason",
    # Profile types
    "AnalysisProfile",
    "FinancialLiteracy",
    # Domain utilities
    "regime_confidence_score",
    # Options positioning utilities
    "signal_agreement_direction",
    "iv_percentile_rank",
    # Integration ports — implement these to plug in a custom persistence backend
    "Storage",
    "CacheBackend",
    "StockRepository",
    "AnalysisProfileRepository",
]
