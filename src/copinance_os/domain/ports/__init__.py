"""Domain ports (interfaces) for external dependencies."""

from copinance_os.domain.models.tool_results import ToolResult
from copinance_os.domain.ports.analysis_execution import (
    AnalysisExecutor,
    AnalyzeInstrumentRunner,
    AnalyzeMarketRunner,
    JobRunner,
)
from copinance_os.domain.ports.analytics import OptionsChainGreeksEstimator
from copinance_os.domain.ports.analyzers import LLMAnalyzer
from copinance_os.domain.ports.data_providers import (
    AlternativeDataProvider,
    DataProvider,
    FundamentalDataProvider,
    MacroeconomicDataProvider,
    MarketDataProvider,
)
from copinance_os.domain.ports.repositories import (
    AnalysisProfileRepository,
    StockRepository,
)
from copinance_os.domain.ports.storage import Storage
from copinance_os.domain.ports.tools import (
    Tool,
    ToolParameter,
    ToolSchema,
)
from copinance_os.domain.ports.use_cases import UseCase
from copinance_os.domain.strategies.protocols import (
    DueDiligenceStrategy,
    MonitoringStrategy,
    RiskAssessmentStrategy,
    ScreeningStrategy,
    ThematicInvestingStrategy,
    ValuationStrategy,
)

__all__ = [
    "JobRunner",
    "AnalysisExecutor",
    "AnalyzeInstrumentRunner",
    "AnalyzeMarketRunner",
    "UseCase",
    # Repositories
    "AnalysisProfileRepository",
    "StockRepository",
    # Storage
    "Storage",
    # Data Providers
    "DataProvider",
    "MarketDataProvider",
    "OptionsChainGreeksEstimator",
    "AlternativeDataProvider",
    "FundamentalDataProvider",
    "MacroeconomicDataProvider",
    # Analyzers
    "LLMAnalyzer",
    # Strategies
    "ScreeningStrategy",
    "DueDiligenceStrategy",
    "ValuationStrategy",
    "RiskAssessmentStrategy",
    "ThematicInvestingStrategy",
    "MonitoringStrategy",
    # Tools
    "Tool",
    "ToolParameter",
    "ToolResult",
    "ToolSchema",
]
