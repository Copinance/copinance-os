"""Workflow-specific domain models."""

from copinanceos.domain.models.workflows.macro import (
    CommoditiesData,
    CreditData,
    MacroRegimeIndicatorsData,
    MacroRegimeIndicatorsResult,
    MacroRegimeWorkflowResult,
    MacroSeriesData,
    MacroSeriesMetadata,
    RatesData,
)
from copinanceos.domain.models.workflows.market_regime import (
    AnalysisMetadata,
    MarketBreadthData,
    MarketCyclesData,
    MarketRegimeDetectionResult,
    MarketRegimeIndicatorsData,
    MarketRegimeIndicatorsResult,
    MarketTrendData,
    SectorDetail,
    SectorMomentum,
    SectorRotationData,
    VIXData,
    VolatilityRegimeData,
)

__all__ = [
    # Common models
    "AnalysisMetadata",
    "MacroSeriesData",
    "MacroSeriesMetadata",
    # Macro workflow models
    "MacroRegimeWorkflowResult",
    "MacroRegimeIndicatorsResult",
    "MacroRegimeIndicatorsData",
    "RatesData",
    "CreditData",
    "CommoditiesData",
    # Market regime models
    "MarketRegimeIndicatorsResult",
    "MarketRegimeIndicatorsData",
    "MarketRegimeDetectionResult",
    "MarketTrendData",
    "VolatilityRegimeData",
    "MarketCyclesData",
    "VIXData",
    "SectorDetail",
    "MarketBreadthData",
    "SectorMomentum",
    "SectorRotationData",
]
