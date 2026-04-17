"""
Copinance OS - Open-source market analysis platform and framework.

A comprehensive platform for short/mid/long term market analysis with support for
question-driven AI analysis and deterministic instrument/macro analysis pipelines.

Library usage example::

    from copinance_os import (
        AnalyzeInstrumentRequest,
        AnalyzeMarketRequest,
        FinancialLiteracy,
    )
    from copinance_os.infra.di import get_container

    container = get_container()
    runner = container.analyze_instrument_runner()

    result = await runner.run(
        AnalyzeInstrumentRequest(
            symbol="AAPL",
            question="What is the current options positioning?",
            financial_literacy=FinancialLiteracy.INTERMEDIATE,
        )
    )
"""

__version__ = "0.1.0"

# Re-export the most common types for library consumers so they have a single
# stable import path that won't change as internal modules are reorganised.
from copinance_os.domain.models.analysis import (  # noqa: E402
    AnalyzeInstrumentRequest,
    AnalyzeMarketRequest,
    AnalyzeMode,
)
from copinance_os.domain.models.analysis_report import AnalysisReport  # noqa: E402
from copinance_os.domain.models.job import RunJobResult  # noqa: E402
from copinance_os.domain.models.profile import AnalysisProfile, FinancialLiteracy  # noqa: E402

__all__ = [
    "__version__",
    # Request/response types
    "AnalyzeInstrumentRequest",
    "AnalyzeMarketRequest",
    "AnalyzeMode",
    "RunJobResult",
    "AnalysisReport",
    # Profile types
    "AnalysisProfile",
    "FinancialLiteracy",
]
