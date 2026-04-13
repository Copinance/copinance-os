"""Domain models for aggregate options surface / positioning metrics."""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field

from copinance_os.domain.models.base import ValueObject

PositioningWindow = Literal["near", "mid"]
PositioningBias = Literal["bullish", "bearish", "neutral"]
GammaRegime = Literal["positive_gamma", "negative_gamma", "neutral"]
TermStructureSlope = Literal["contango", "backwardation", "flat"]
SkewRegime = Literal["steep_put", "normal", "call_skewed"]
SignalAgreement = Literal[
    "strong_bullish",
    "moderate_bullish",
    "weak_bullish",
    "strong_bearish",
    "moderate_bearish",
    "weak_bearish",
    "mixed",
]


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
    skew_10_delta: float | None = Field(default=None, alias="skew10Delta")
    butterfly_25_delta: float | None = Field(default=None, alias="butterfly25Delta")
    skew_regime: SkewRegime | None = Field(default=None, alias="skewRegime")


class StrikeOIClusterModel(ValueObject):
    model_config = ConfigDict(populate_by_name=True)

    strike: float
    open_interest: float = Field(..., alias="openInterest")


class DollarMetricsModel(ValueObject):
    model_config = ConfigDict(populate_by_name=True)

    dollar_call_oi: float = Field(..., alias="dollarCallOI")
    dollar_put_oi: float = Field(..., alias="dollarPutOI")
    dollar_put_call_oi_ratio: float = Field(..., alias="dollarPutCallOIRatio")
    dollar_call_volume: float = Field(..., alias="dollarCallVolume")
    dollar_put_volume: float = Field(..., alias="dollarPutVolume")
    dollar_call_flow_share: float = Field(..., alias="dollarCallFlowShare")


class GEXStrikeModel(ValueObject):
    model_config = ConfigDict(populate_by_name=True)

    strike: float
    gex_value: float = Field(..., alias="gexValue")


class DeltaExposureModel(ValueObject):
    model_config = ConfigDict(populate_by_name=True)

    net_delta: float = Field(..., alias="netDelta")
    dollar_delta: float = Field(..., alias="dollarDelta")
    call_delta_exposure: float = Field(..., alias="callDeltaExposure")
    put_delta_exposure: float = Field(..., alias="putDeltaExposure")


class EnhancedStrikeOIClusterModel(ValueObject):
    model_config = ConfigDict(populate_by_name=True)

    strike: float
    call_oi: float = Field(..., alias="callOI")
    put_oi: float = Field(..., alias="putOI")
    total_oi: float = Field(..., alias="totalOI")
    put_call_ratio: float = Field(..., alias="putCallRatio")


class ImpliedMoveDetailModel(ValueObject):
    model_config = ConfigDict(populate_by_name=True)

    raw_straddle_pct: float = Field(..., alias="rawStraddlePct")
    raw_straddle_abs: float = Field(..., alias="rawStraddleAbs")
    dte: int
    annualized_iv: float = Field(..., alias="annualizedIV")
    daily_implied_move_pct: float = Field(..., alias="dailyImpliedMovePct")
    period_implied_move_pct: float = Field(..., alias="periodImpliedMovePct")


class VannaStrikeModel(ValueObject):
    model_config = ConfigDict(populate_by_name=True)

    strike: float
    vanna_exposure: float = Field(..., alias="vannaExposure")


class VannaExposureModel(ValueObject):
    model_config = ConfigDict(populate_by_name=True)

    net_vanna: float = Field(..., alias="netVanna")
    call_vanna_exposure: float = Field(..., alias="callVannaExposure")
    put_vanna_exposure: float = Field(..., alias="putVannaExposure")
    vanna_flip_strike: float | None = Field(default=None, alias="vannaFlipStrike")
    regime: str = Field(default="neutral")


class CharmExposureModel(ValueObject):
    model_config = ConfigDict(populate_by_name=True)

    net_charm: float = Field(..., alias="netCharm")
    call_charm_exposure: float = Field(..., alias="callCharmExposure")
    put_charm_exposure: float = Field(..., alias="putCharmExposure")
    overnight_delta_drift: str = Field(default="neutral")


class MispricingModel(ValueObject):
    model_config = ConfigDict(populate_by_name=True)

    call_avg_mispricing_pct: float = Field(..., alias="callAvgMispricingPct")
    put_avg_mispricing_pct: float = Field(..., alias="putAvgMispricingPct")
    overpriced_call_pct: float = Field(..., alias="overpricedCallPct")
    overpriced_put_pct: float = Field(..., alias="overpricedPutPct")
    sentiment: str = Field(default="neutral")


class MoneynessBucket(ValueObject):
    model_config = ConfigDict(populate_by_name=True)

    bucket: str
    call_oi: int = Field(default=0, alias="callOI")
    put_oi: int = Field(default=0, alias="putOI")
    call_volume: int = Field(default=0, alias="callVolume")
    put_volume: int = Field(default=0, alias="putVolume")
    dollar_call_volume: float = Field(default=0.0, alias="dollarCallVolume")
    dollar_put_volume: float = Field(default=0.0, alias="dollarPutVolume")


class MoneynessSummaryModel(ValueObject):
    model_config = ConfigDict(populate_by_name=True)

    buckets: list[MoneynessBucket] = Field(default_factory=list)
    dominant_call_bucket: str | None = Field(default=None, alias="dominantCallBucket")
    dominant_put_bucket: str | None = Field(default=None, alias="dominantPutBucket")


class PinRiskStrikeModel(ValueObject):
    model_config = ConfigDict(populate_by_name=True)

    strike: float
    total_oi: int = Field(..., alias="totalOI")
    expected_exercised: float = Field(..., alias="expectedExercised")
    pin_score: float = Field(..., alias="pinScore")


class PinRiskModel(ValueObject):
    model_config = ConfigDict(populate_by_name=True)

    max_pin_strike: float | None = Field(default=None, alias="maxPinStrike")
    pin_risk_level: str = Field(default="low")
    dte: int | None = None
    top_strikes: list[PinRiskStrikeModel] = Field(default_factory=list, alias="topStrikes")


class SignalCategoriesModel(ValueObject):
    model_config = ConfigDict(populate_by_name=True)

    positioning: list[PositioningMetricModel] = Field(default_factory=list)
    volatility: list[PositioningMetricModel] = Field(default_factory=list)
    flow: list[PositioningMetricModel] = Field(default_factory=list)
    gamma: list[PositioningMetricModel] = Field(default_factory=list)
    structure: list[PositioningMetricModel] = Field(default_factory=list)


class MethodologyReferenceModel(ValueObject):
    id: str
    title: str
    url: str


class MethodologyModel(ValueObject):
    model_config = ConfigDict(populate_by_name=True)

    version: str
    computed_at: str = Field(..., alias="computedAt")
    model_family: str = Field(..., alias="modelFamily")
    assumptions: list[str]
    limitations: list[str]
    references: list[MethodologyReferenceModel]
    data_inputs: dict[str, str] = Field(..., alias="dataInputs")


class OptionsPositioningResult(ValueObject):
    """Full options-intelligence payload (internal snake_case; aliases for API JSON)."""

    model_config = ConfigDict(populate_by_name=True)

    symbol: str
    window: PositioningWindow
    methodology: MethodologyModel
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
    data_quality: float | None = Field(default=None, ge=0, le=1, alias="dataQuality")
    dollar_metrics: DollarMetricsModel | None = Field(default=None, alias="dollarMetrics")
    gamma_flip_strike: float | None = Field(default=None, alias="gammaFlipStrike")
    gex_profile: list[GEXStrikeModel] = Field(default_factory=list, alias="gexProfile")
    top_positive_gex: list[GEXStrikeModel] = Field(default_factory=list, alias="topPositiveGex")
    top_negative_gex: list[GEXStrikeModel] = Field(default_factory=list, alias="topNegativeGex")
    delta_exposure: DeltaExposureModel | None = Field(default=None, alias="deltaExposure")
    oi_clusters_enhanced: list[EnhancedStrikeOIClusterModel] = Field(
        default_factory=list, alias="oiClustersEnhanced"
    )
    call_wall: float | None = Field(default=None, alias="callWall")
    put_wall: float | None = Field(default=None, alias="putWall")
    implied_move_detail: ImpliedMoveDetailModel | None = Field(
        default=None, alias="impliedMoveDetail"
    )
    signal_agreement: SignalAgreement | None = Field(default=None, alias="signalAgreement")
    vanna_exposure: VannaExposureModel | None = Field(default=None, alias="vannaExposure")
    vanna_profile: list[VannaStrikeModel] = Field(default_factory=list, alias="vannaProfile")
    charm_exposure: CharmExposureModel | None = Field(default=None, alias="charmExposure")
    mispricing: MispricingModel | None = None
    moneyness_summary: MoneynessSummaryModel | None = Field(default=None, alias="moneynessSummary")
    pin_risk: PinRiskModel | None = Field(default=None, alias="pinRisk")
