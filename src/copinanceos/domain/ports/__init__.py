"""Domain ports (interfaces) for external dependencies."""

from copinanceos.domain.models.tool_results import ToolResult
from copinanceos.domain.ports.analysis_execution import AnalysisExecutor, JobRunner
from copinanceos.domain.ports.analytics import OptionsChainGreeksEstimator
from copinanceos.domain.ports.analyzers import LLMAnalyzer
from copinanceos.domain.ports.data_providers import (
    AlternativeDataProvider,
    DataProvider,
    FundamentalDataProvider,
    MacroeconomicDataProvider,
    MarketDataProvider,
)
from copinanceos.domain.ports.repositories import (
    AnalysisProfileRepository,
    StockRepository,
)
from copinanceos.domain.ports.storage import Storage
from copinanceos.domain.ports.strategies import (
    DueDiligenceStrategy,
    MonitoringStrategy,
    RiskAssessmentStrategy,
    ScreeningStrategy,
    ThematicInvestingStrategy,
    ValuationStrategy,
)
from copinanceos.domain.ports.tools import (
    Tool,
    ToolParameter,
    ToolSchema,
)

__all__ = [
    "JobRunner",
    "AnalysisExecutor",
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
