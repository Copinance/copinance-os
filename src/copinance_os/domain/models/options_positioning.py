"""Domain models for aggregate options surface / positioning metrics."""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field

from copinance_os.domain.models.base import ValueObject

PositioningWindow = Literal["near", "mid"]
PositioningBias = Literal["bullish", "bearish", "neutral"]
GammaRegime = Literal["positive_gamma", "negative_gamma", "neutral"]
TermStructureSlope = Literal["contango", "backwardation", "flat"]


class PositioningMetricModel(ValueObject):
    """Single named metric with direction and copy."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    value: float
    direction: Literal["bullish", "bearish", "neutral"]
    explanation: str


class PositioningScenarioModel(ValueObject):
    label: str
    probability: float = Field(..., ge=0, le=1)
    narrative: str


class IVMetricsModel(ValueObject):
    model_config = ConfigDict(populate_by_name=True)

    atm_iv: float = Field(..., alias="atmIV")
    skew_25_delta: float = Field(..., alias="skew25Delta")
    term_structure_slope: TermStructureSlope = Field(..., alias="termStructureSlope")
    near_term_atm_iv: float = Field(..., alias="nearTermATMIV")
    far_term_atm_iv: float = Field(..., alias="farTermATMIV")


class StrikeOIClusterModel(ValueObject):
    model_config = ConfigDict(populate_by_name=True)

    strike: float
    open_interest: float = Field(..., alias="openInterest")


class SignalCategoriesModel(ValueObject):
    model_config = ConfigDict(populate_by_name=True)

    positioning: list[PositioningMetricModel] = Field(default_factory=list)
    volatility: list[PositioningMetricModel] = Field(default_factory=list)
    flow: list[PositioningMetricModel] = Field(default_factory=list)
    gamma: list[PositioningMetricModel] = Field(default_factory=list)
    structure: list[PositioningMetricModel] = Field(default_factory=list)


class OptionsPositioningResult(ValueObject):
    """Full options-intelligence payload (internal snake_case; aliases for API JSON)."""

    model_config = ConfigDict(populate_by_name=True)

    symbol: str
    window: PositioningWindow
    confidence: float = Field(..., ge=0, le=1)
    market_bias: PositioningBias = Field(..., alias="marketBias")
    bullish_probability: float = Field(..., ge=0, le=1, alias="bullishProbability")
    bearish_probability: float = Field(..., ge=0, le=1, alias="bearishProbability")
    neutral_probability: float = Field(..., ge=0, le=1, alias="neutralProbability")
    key_levels: list[float] = Field(..., alias="keyLevels")
    analyst_summary: str = Field(..., alias="analystSummary")
    signals: list[PositioningMetricModel]
    scenarios: list[PositioningScenarioModel]
    signal_categories: SignalCategoriesModel | None = Field(default=None, alias="signalCategories")
    regime: GammaRegime | None = None
    regime_explanation: str | None = Field(default=None, alias="regimeExplanation")
    iv_metrics: IVMetricsModel | None = Field(default=None, alias="ivMetrics")
    max_pain: float | None = Field(default=None, alias="maxPain")
    implied_move: float | None = Field(default=None, alias="impliedMove")
    implied_move_absolute: float | None = Field(default=None, alias="impliedMoveAbsolute")
    oi_clusters: list[StrikeOIClusterModel] = Field(default_factory=list, alias="oiClusters")
