"""Domain models for Copinance OS."""

from copinance_os.domain.models.analysis_report import AnalysisReport
from copinance_os.domain.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    FinancialRatios,
    FinancialStatementPeriod,
    IncomeStatement,
    StockFundamentals,
)
from copinance_os.domain.models.job import Job, JobScope, JobStatus, JobTimeframe, RunJobResult
from copinance_os.domain.models.macro import MacroDataPoint
from copinance_os.domain.models.market import (
    MarketDataPoint,
    MarketType,
    OptionContract,
    OptionGreeks,
    OptionsChain,
    OptionSide,
)
from copinance_os.domain.models.profile import AnalysisProfile, FinancialLiteracy
from copinance_os.domain.models.regime import (
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
from copinance_os.domain.models.stock import Stock
from copinance_os.domain.models.tool_results import (
    ToolResult,
)

__all__ = [
    "AnalysisReport",
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
