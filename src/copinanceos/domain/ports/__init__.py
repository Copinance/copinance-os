"""Domain ports (interfaces) for external dependencies."""

from copinanceos.domain.models.tool_results import ToolResult
from copinanceos.domain.ports.analyzers import LLMAnalyzer
from copinanceos.domain.ports.data_providers import (
    AlternativeDataProvider,
    DataProvider,
    FundamentalDataProvider,
    MacroeconomicDataProvider,
    MarketDataProvider,
)
from copinanceos.domain.ports.repositories import (
    ResearchProfileRepository,
    ResearchRepository,
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
from copinanceos.domain.ports.workflows import WorkflowExecutor

__all__ = [
    # Repositories
    "ResearchProfileRepository",
    "ResearchRepository",
    "StockRepository",
    # Storage
    "Storage",
    # Workflows
    "WorkflowExecutor",
    # Data Providers
    "DataProvider",
    "MarketDataProvider",
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
