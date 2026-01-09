"""Macro regime workflow domain models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# Macro Regime Indicators Models
class MacroSeriesData(BaseModel):
    """Data for a macroeconomic time series."""

    available: bool = Field(..., description="Whether series data is available")
    latest: dict[str, Any] | None = Field(
        None, description="Latest data point with timestamp and value"
    )
    data_points: int = Field(default=0, description="Number of data points available")
    change_20d: float | None = Field(None, description="20-day change")
    unit: str | None = Field(None, description="Data unit (e.g., 'percent', 'usd_per_barrel')")
    error: str | None = Field(None, description="Error message if data is not available")


class MacroSeriesMetadata(BaseModel):
    """Metadata for macro series analysis."""

    lookback_days: int = Field(..., description="Number of days used for analysis")


class RatesData(BaseModel):
    """Interest rates analysis data."""

    available: bool = Field(..., description="Whether rates data is available")
    source: str = Field(..., description="Data source (e.g., 'fred', 'yfinance')")
    series: dict[str, MacroSeriesData] = Field(
        default_factory=dict, description="Individual rate series data"
    )
    interpretation: dict[str, Any] = Field(
        default_factory=dict, description="Human-readable interpretation"
    )
    metadata: MacroSeriesMetadata = Field(..., description="Analysis metadata")


class CreditData(BaseModel):
    """Credit spreads analysis data."""

    available: bool = Field(..., description="Whether credit data is available")
    source: str = Field(..., description="Data source (e.g., 'fred', 'yfinance')")
    series: dict[str, MacroSeriesData] = Field(
        default_factory=dict, description="Individual credit series data"
    )
    interpretation: dict[str, Any] = Field(
        default_factory=dict, description="Human-readable interpretation"
    )
    metadata: MacroSeriesMetadata = Field(..., description="Analysis metadata")


class CommoditiesData(BaseModel):
    """Commodities analysis data."""

    available: bool = Field(..., description="Whether commodities data is available")
    source: str = Field(..., description="Data source (e.g., 'fred', 'yfinance')")
    series: dict[str, MacroSeriesData] = Field(
        default_factory=dict, description="Individual commodity series data"
    )
    interpretation: dict[str, Any] = Field(
        default_factory=dict, description="Human-readable interpretation"
    )
    metadata: MacroSeriesMetadata = Field(..., description="Analysis metadata")


class LaborData(BaseModel):
    """Labor market analysis data."""

    available: bool = Field(..., description="Whether labor data is available")
    source: str = Field(..., description="Data source (e.g., 'fred', 'yfinance')")
    series: dict[str, MacroSeriesData] = Field(
        default_factory=dict, description="Individual labor series data"
    )
    interpretation: dict[str, Any] = Field(
        default_factory=dict, description="Human-readable interpretation"
    )
    metadata: MacroSeriesMetadata = Field(..., description="Analysis metadata")


class HousingData(BaseModel):
    """Housing market analysis data."""

    available: bool = Field(..., description="Whether housing data is available")
    source: str = Field(..., description="Data source (e.g., 'fred', 'yfinance')")
    series: dict[str, MacroSeriesData] = Field(
        default_factory=dict, description="Individual housing series data"
    )
    interpretation: dict[str, Any] = Field(
        default_factory=dict, description="Human-readable interpretation"
    )
    metadata: MacroSeriesMetadata = Field(..., description="Analysis metadata")


class ManufacturingData(BaseModel):
    """Manufacturing analysis data."""

    available: bool = Field(..., description="Whether manufacturing data is available")
    source: str = Field(..., description="Data source (e.g., 'fred', 'yfinance')")
    series: dict[str, MacroSeriesData] = Field(
        default_factory=dict, description="Individual manufacturing series data"
    )
    interpretation: dict[str, Any] = Field(
        default_factory=dict, description="Human-readable interpretation"
    )
    metadata: MacroSeriesMetadata = Field(..., description="Analysis metadata")


class ConsumerData(BaseModel):
    """Consumer analysis data."""

    available: bool = Field(..., description="Whether consumer data is available")
    source: str = Field(..., description="Data source (e.g., 'fred', 'yfinance')")
    series: dict[str, MacroSeriesData] = Field(
        default_factory=dict, description="Individual consumer series data"
    )
    interpretation: dict[str, Any] = Field(
        default_factory=dict, description="Human-readable interpretation"
    )
    metadata: MacroSeriesMetadata = Field(..., description="Analysis metadata")


class GlobalData(BaseModel):
    """Global market analysis data."""

    available: bool = Field(..., description="Whether global data is available")
    source: str = Field(..., description="Data source (e.g., 'fred', 'yfinance')")
    series: dict[str, MacroSeriesData] = Field(
        default_factory=dict, description="Individual global series data"
    )
    interpretation: dict[str, Any] = Field(
        default_factory=dict, description="Human-readable interpretation"
    )
    metadata: MacroSeriesMetadata = Field(..., description="Analysis metadata")


class AdvancedData(BaseModel):
    """Advanced economic indicators data."""

    available: bool = Field(..., description="Whether advanced data is available")
    source: str = Field(..., description="Data source (e.g., 'fred', 'yfinance')")
    series: dict[str, MacroSeriesData] = Field(
        default_factory=dict, description="Individual advanced series data"
    )
    interpretation: dict[str, Any] = Field(
        default_factory=dict, description="Human-readable interpretation"
    )
    metadata: MacroSeriesMetadata = Field(..., description="Analysis metadata")


class MacroRegimeIndicatorsData(BaseModel):
    """Complete macro regime indicators data structure."""

    rates: RatesData | None = Field(None, description="Interest rates analysis")
    credit: CreditData | None = Field(None, description="Credit spreads analysis")
    commodities: CommoditiesData | None = Field(None, description="Commodities analysis")
    labor: LaborData | None = Field(None, description="Labor market analysis")
    housing: HousingData | None = Field(None, description="Housing market analysis")
    manufacturing: ManufacturingData | None = Field(None, description="Manufacturing analysis")
    consumer: ConsumerData | None = Field(None, description="Consumer analysis")
    global_data: GlobalData | None = Field(None, description="Global market analysis")
    advanced: AdvancedData | None = Field(None, description="Advanced economic indicators")


# Import ToolResult from the tool results
from copinanceos.domain.models.tool_results import ToolResult

# Import required models for type annotations
from copinanceos.domain.models.workflows.market_regime import (
    MarketRegimeDetectionResult,
    MarketRegimeIndicatorsResult,
)


class MacroRegimeIndicatorsResult(ToolResult[MacroRegimeIndicatorsData]):
    """Result from macro regime indicators tool."""


class MacroRegimeWorkflowResult(BaseModel):
    """Complete result from macro regime workflow execution.

    This model represents the complete output structure from the macro workflow,
    combining market regime indicators, regime detection, and macro indicators.
    """

    analysis_type: Literal["macro_and_market_regime_static"] = Field(
        default="macro_and_market_regime_static",
        description="Type of analysis performed",
    )
    market_index: str = Field(..., description="Market index symbol analyzed (e.g., SPY, QQQ)")
    execution_timestamp: datetime = Field(..., description="When the analysis was executed")

    market_regime_indicators: MarketRegimeIndicatorsResult = Field(
        ..., description="Market regime indicators (VIX, breadth, sector rotation)"
    )
    market_regime_detection: MarketRegimeDetectionResult = Field(
        ..., description="Rule-based regime detection results"
    )
    macro_regime_indicators: MacroRegimeIndicatorsResult = Field(
        ..., description="Macro regime indicators (rates, credit, commodities)"
    )

    status: str | None = Field(None, description="Workflow execution status")
    error: str | None = Field(None, description="Error message if workflow failed")

    model_config = {"extra": "allow"}  # Allow additional fields for future extensibility
