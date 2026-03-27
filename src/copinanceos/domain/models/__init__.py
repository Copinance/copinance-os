"""Domain models for Copinance OS."""

from copinanceos.domain.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    FinancialRatios,
    FinancialStatementPeriod,
    IncomeStatement,
    StockFundamentals,
)
from copinanceos.domain.models.job import Job, JobScope, JobStatus, JobTimeframe, RunJobResult
from copinanceos.domain.models.macro import MacroDataPoint
from copinanceos.domain.models.market import (
    MarketDataPoint,
    MarketType,
    OptionContract,
    OptionGreeks,
    OptionsChain,
    OptionSide,
)
from copinanceos.domain.models.profile import AnalysisProfile, FinancialLiteracy
from copinanceos.domain.models.regime import (
    AnalysisMetadata,
    CommoditiesData,
    CreditData,
    MacroRegimeIndicatorsData,
    MacroRegimeIndicatorsResult,
    MacroRegimeResult,
    MacroSeriesData,
    MacroSeriesMetadata,
    MarketBreadthData,
    MarketCyclesData,
    MarketRegimeDetectionResult,
    MarketRegimeIndicatorsData,
    MarketRegimeIndicatorsResult,
    MarketTrendData,
    RatesData,
    SectorDetail,
    SectorMomentum,
    SectorRotationData,
    VIXData,
    VolatilityRegimeData,
)
from copinanceos.domain.models.stock import Stock
from copinanceos.domain.models.tool_results import (
    ToolResult,
)

__all__ = [
    "Job",
    "JobScope",
    "JobStatus",
    "JobTimeframe",
    "RunJobResult",
    "AnalysisProfile",
    "FinancialLiteracy",
    "Stock",
    "MarketType",
    "OptionSide",
    "MarketDataPoint",
    "OptionContract",
    "OptionGreeks",
    "OptionsChain",
    "MacroDataPoint",
    "StockFundamentals",
    "IncomeStatement",
    "BalanceSheet",
    "CashFlowStatement",
    "FinancialRatios",
    "FinancialStatementPeriod",
    # Core Framework Models
    "ToolResult",
    # Regime/macro models (imported from regime package)
    "AnalysisMetadata",
    "MacroSeriesData",
    "MacroSeriesMetadata",
    "VIXData",
    "SectorDetail",
    "MarketBreadthData",
    "SectorMomentum",
    "SectorRotationData",
    "MarketRegimeIndicatorsData",
    "MarketRegimeIndicatorsResult",
    "MarketTrendData",
    "VolatilityRegimeData",
    "MarketCyclesData",
    "MarketRegimeDetectionResult",
    "RatesData",
    "CreditData",
    "CommoditiesData",
    "MacroRegimeIndicatorsData",
    "MacroRegimeIndicatorsResult",
    "MacroRegimeResult",
]
