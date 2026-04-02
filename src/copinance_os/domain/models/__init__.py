"""Domain models for Copinance OS."""

from copinance_os.domain.models.analysis import (
    INSTRUMENT_DETERMINISTIC_TYPE,
    INSTRUMENT_QUESTION_DRIVEN_TYPE,
    MARKET_DETERMINISTIC_TYPE,
    MARKET_QUESTION_DRIVEN_TYPE,
    AnalyzeInstrumentRequest,
    AnalyzeMarketRequest,
    AnalyzeMode,
    execution_type_from_scope_and_mode,
    get_default_instrument_timeframe,
    resolve_analyze_mode,
)
from copinance_os.domain.models.analysis_report import AnalysisReport
from copinance_os.domain.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    FinancialRatios,
    FinancialStatementPeriod,
    GetStockFundamentalsRequest,
    GetStockFundamentalsResponse,
    IncomeStatement,
    StockFundamentals,
)
from copinance_os.domain.models.job import (
    Job,
    JobScope,
    JobStatus,
    JobTimeframe,
    ReportExclusionReason,
    RunJobResult,
)
from copinance_os.domain.models.macro import MacroDataPoint
from copinance_os.domain.models.market import (
    MarketDataPoint,
    MarketType,
    OptionContract,
    OptionGreeks,
    OptionsChain,
    OptionSide,
)
from copinance_os.domain.models.market_requests import (
    GetHistoricalDataRequest,
    GetHistoricalDataResponse,
    GetInstrumentRequest,
    GetInstrumentResponse,
    GetOptionsChainRequest,
    GetOptionsChainResponse,
    GetQuoteRequest,
    GetQuoteResponse,
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
from copinance_os.domain.models.tool_bundle_context import ToolBundleContext
from copinance_os.domain.models.tool_results import (
    ToolResult,
)

__all__ = [
    "AnalysisReport",
    # Analysis request models
    "AnalyzeInstrumentRequest",
    "AnalyzeMarketRequest",
    "AnalyzeMode",
    "INSTRUMENT_DETERMINISTIC_TYPE",
    "INSTRUMENT_QUESTION_DRIVEN_TYPE",
    "MARKET_DETERMINISTIC_TYPE",
    "MARKET_QUESTION_DRIVEN_TYPE",
    "execution_type_from_scope_and_mode",
    "get_default_instrument_timeframe",
    "resolve_analyze_mode",
    # Market request models
    "GetInstrumentRequest",
    "GetInstrumentResponse",
    "GetQuoteRequest",
    "GetQuoteResponse",
    "GetHistoricalDataRequest",
    "GetHistoricalDataResponse",
    "GetOptionsChainRequest",
    "GetOptionsChainResponse",
    # Fundamentals request models
    "GetStockFundamentalsRequest",
    "GetStockFundamentalsResponse",
    # Job models
    "Job",
    "JobScope",
    "JobStatus",
    "JobTimeframe",
    "RunJobResult",
    "ReportExclusionReason",
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
    "ToolBundleContext",
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
