"""Market regime workflow domain models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# Market Regime Indicators Models
class VIXData(BaseModel):
    """VIX (volatility index) data structure."""

    available: bool = Field(..., description="Whether VIX data is available")
    current_vix: float | None = Field(None, description="Current VIX level")
    recent_average_20d: float | None = Field(None, description="20-day average VIX level")
    recent_max_20d: float | None = Field(None, description="Maximum VIX in last 20 days")
    recent_min_20d: float | None = Field(None, description="Minimum VIX in last 20 days")
    regime: Literal["low", "normal", "high", "very_high"] | None = Field(
        None, description="VIX regime classification"
    )
    sentiment: Literal["complacent", "normal", "fearful", "panic"] | None = Field(
        None, description="Market sentiment based on VIX"
    )
    data_points: int = Field(..., description="Number of data points used")


class SectorDetail(BaseModel):
    """Detailed performance data for a sector ETF."""

    name: str = Field(..., description="Sector name")
    current_price: float = Field(..., description="Current sector ETF price")
    above_50ma: bool = Field(..., description="Whether sector is above its 50-day MA")
    relative_performance_pct: float = Field(
        ..., description="Sector return vs. market return (percentage)"
    )
    sector_return_pct: float = Field(..., description="Sector return percentage")
    market_return_pct: float = Field(..., description="Market return percentage")


class MarketBreadthData(BaseModel):
    """Market breadth analysis data structure."""

    available: bool = Field(..., description="Whether market breadth data is available")
    breadth_ratio: float | None = Field(
        None, description="Percentage of sectors above 50-day moving average"
    )
    participation_ratio: float | None = Field(
        None, description="Percentage of sectors outperforming the market"
    )
    sectors_above_50ma: int = Field(..., description="Count of sectors above their 50-day MA")
    sectors_outperforming: int = Field(..., description="Count of sectors outperforming the market")
    total_sectors_analyzed: int = Field(..., description="Total number of sectors analyzed")
    regime: Literal["strong", "moderate", "weak"] | None = Field(
        None, description="Breadth regime classification"
    )
    sector_details: dict[str, SectorDetail] = Field(
        default_factory=dict, description="Detailed performance for each sector ETF"
    )


class SectorMomentum(BaseModel):
    """Momentum data for a sector ETF."""

    symbol: str = Field(..., description="Sector ETF symbol")
    name: str = Field(..., description="Sector name")
    momentum_score: float = Field(..., description="Weighted momentum score (20d: 60%, 60d: 40%)")
    relative_momentum_20d: float = Field(..., description="Sector momentum vs. market (20-day)")
    relative_momentum_60d: float = Field(..., description="Sector momentum vs. market (60-day)")
    sector_return_20d: float = Field(..., description="Sector return over last 20 days")
    sector_return_60d: float = Field(..., description="Sector return over last 60 days")


class SectorRotationData(BaseModel):
    """Sector rotation analysis data structure."""

    available: bool = Field(..., description="Whether sector rotation data is available")
    rotation_theme: Literal["defensive", "growth", "value", "mixed"] | None = Field(
        None, description="Overall rotation theme"
    )
    leading_sectors: list[SectorMomentum] = Field(
        default_factory=list, description="Top 3 sectors by momentum score"
    )
    lagging_sectors: list[SectorMomentum] = Field(
        default_factory=list, description="Bottom 3 sectors by momentum score"
    )
    all_sectors_ranked: list[SectorMomentum] = Field(
        default_factory=list, description="All sectors sorted by momentum score (highest first)"
    )
    market_return_20d: float = Field(
        ..., description="Market return over last 20 days (percentage)"
    )
    market_return_60d: float = Field(
        ..., description="Market return over last 60 days (percentage)"
    )


class MarketRegimeIndicatorsData(BaseModel):
    """Complete market regime indicators data structure."""

    vix: VIXData | None = Field(None, description="VIX volatility index data")
    market_breadth: MarketBreadthData | None = Field(None, description="Market breadth analysis")
    sector_rotation: SectorRotationData | None = Field(None, description="Sector rotation signals")


# Import ToolResult from the tool results
from copinanceos.domain.models.tool_results import ToolResult


class MarketRegimeIndicatorsResult(ToolResult[MarketRegimeIndicatorsData]):
    """Result from market regime indicators tool."""


# Common analysis metadata to reduce duplication
class AnalysisMetadata(BaseModel):
    """Common metadata shared across analysis results."""

    analysis_period_days: int = Field(..., description="Analysis period in days")
    data_points: int = Field(..., description="Number of data points used")
    parameters_adjusted: bool = Field(
        ..., description="Whether parameters were adjusted due to limited data"
    )


# Market Regime Detection Models
class MarketTrendData(BaseModel):
    """Market trend detection result data."""

    regime: Literal["bull", "bear", "sideways"] = Field(..., description="Detected trend regime")
    confidence: Literal["high", "medium", "low"] | float = Field(
        ..., description="Confidence level in the detection"
    )
    current_price: float = Field(..., description="Current price")
    price_change_pct: float = Field(..., description="Price change percentage")
    log_return: float = Field(..., description="Logarithmic return")
    volatility_scaled_momentum: float = Field(..., description="Volatility-scaled momentum score")
    recent_volatility: float = Field(..., description="Recent volatility percentage")
    momentum_20d_pct: float = Field(..., description="20-day momentum percentage")
    short_ma: float = Field(..., description="Short-term moving average")
    long_ma: float = Field(..., description="Long-term moving average")
    ma_relationship: Literal["bullish", "bearish", "neutral"] = Field(
        ..., description="Moving average relationship"
    )
    short_ma_period_used: int = Field(..., description="Short MA period actually used")
    long_ma_period_used: int = Field(..., description="Long MA period actually used")
    methodology: str = Field(..., description="Detection methodology used")
    note: str | None = Field(None, description="Additional notes about the analysis")
    metadata: AnalysisMetadata = Field(..., description="Analysis metadata")


class VolatilityRegimeData(BaseModel):
    """Volatility regime detection result data."""

    regime: Literal["low", "normal", "high"] = Field(..., description="Detected volatility regime")
    current_volatility: float = Field(..., description="Current volatility percentage")
    mean_volatility: float = Field(..., description="Mean volatility over analysis period")
    max_volatility: float = Field(..., description="Maximum volatility over analysis period")
    min_volatility: float = Field(..., description="Minimum volatility over analysis period")
    volatility_percentile: float = Field(..., description="Volatility percentile")
    volatility_window: int = Field(..., description="Volatility calculation window")
    metadata: AnalysisMetadata = Field(..., description="Analysis metadata")


class MarketCyclesData(BaseModel):
    """Market cycles detection result data."""

    current_phase: Literal["accumulation", "markup", "distribution", "markdown"] = Field(
        ..., description="Current market cycle phase"
    )
    phase_description: str = Field(..., description="Human-readable phase description")
    price_position_pct: float = Field(..., description="Price position within cycle (percentage)")
    volume_ratio: float = Field(..., description="Volume ratio vs. moving average")
    current_price: float = Field(..., description="Current price")
    ma_20: float = Field(..., description="20-day moving average")
    ma_50: float = Field(..., description="50-day moving average")
    recent_trend: Literal["up", "down", "sideways"] = Field(..., description="Recent price trend")
    longer_trend: Literal["up", "down", "sideways"] = Field(..., description="Longer-term trend")
    potential_regime_change: bool = Field(..., description="Whether regime change is signaled")
    ma_short_period_used: int = Field(..., description="Short MA period actually used")
    ma_long_period_used: int = Field(..., description="Long MA period actually used")
    metadata: AnalysisMetadata = Field(..., description="Analysis metadata")


class MarketRegimeDetectionResult(BaseModel):
    """Results from market regime detection tools."""

    symbol: str = Field(..., description="Stock/market symbol analyzed")
    detect_market_trend: MarketTrendData | None = Field(
        None, description="Market trend detection result"
    )
    detect_volatility_regime: VolatilityRegimeData | None = Field(
        None, description="Volatility regime detection result"
    )
    detect_market_cycles: MarketCyclesData | None = Field(
        None, description="Market cycles detection result"
    )
