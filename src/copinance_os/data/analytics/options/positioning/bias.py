"""Aggregate directional bias score and signal agreement."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, cast

from copinance_os.data.analytics.options.positioning.math import normalize, sigmoid
from copinance_os.domain.models.methodology import MethodologyReference, MethodologySpec
from copinance_os.domain.models.options_positioning import SignalAgreement

REF_BOLLEN_WHALEY_2004 = MethodologyReference(
    id="REF_BOLLEN_WHALEY_2004",
    title="Bollen and Whaley (2004), Does Net Buying Pressure Affect the Shape of Implied Volatility Functions?",
    url="https://doi.org/10.1111/j.1540-6261.2004.00663.x",
)
REF_PAN_POTESHMAN_2006 = MethodologyReference(
    id="REF_PAN_POTESHMAN_2006",
    title="Pan and Poteshman (2006), The Information in Option Volume for Future Stock Prices",
    url="https://doi.org/10.1093/rfs/hhj021",
)


@dataclass(frozen=True, slots=True)
class BiasConfig:
    ranges: Mapping[str, tuple[float, float]] = field(
        default_factory=lambda: {
            "call_oi_ratio": (0.35, 0.65),
            "call_flow_share": (0.35, 0.65),
            "gamma_tilt": (-0.4, 0.4),
            "put_call_oi_ratio": (0.7, 1.6),
            "dollar_put_call_oi_ratio": (0.7, 1.6),
            "net_delta": (-500_000.0, 500_000.0),
        }
    )
    weights: Mapping[str, float] = field(
        default_factory=lambda: {
            "call_oi_ratio": 1.8,
            "call_flow_share": 1.6,
            "gamma_tilt": 1.4,
            "put_call_oi_ratio": -1.2,
            "dollar_put_call_oi_ratio": -1.4,
            "net_delta": 1.2,
        }
    )
    mid_window_damping: float = 0.8


DEFAULT_BIAS_CONFIG = BiasConfig()


def bias_methodology(config: BiasConfig) -> MethodologySpec:
    return MethodologySpec(
        id="options.positioning.bias",
        version="v1",
        model_family="weighted_sigmoid_bias",
        assumptions=("Fixed transparent weights across OI/flow/Greek tilts.",),
        limitations=("Heuristic; not execution advice.",),
        references=(REF_BOLLEN_WHALEY_2004, REF_PAN_POTESHMAN_2006),
        parameters={
            "weights": str(dict(config.weights)),
            "ranges": str(dict(config.ranges)),
            "mid_window_damping": str(config.mid_window_damping),
        },
    )


def compute_bias_score(
    call_oi_ratio: float,
    call_flow_share: float,
    gamma_tilt: float,
    put_call_oi_ratio: float,
    dollar_put_call_oi_ratio: float,
    net_delta: float,
    dollar_call_oi: float,
    config: BiasConfig = DEFAULT_BIAS_CONFIG,
) -> float:
    score = 0.0
    for key, weight in config.weights.items():
        if key == "call_oi_ratio":
            val = call_oi_ratio
        elif key == "call_flow_share":
            val = call_flow_share
        elif key == "gamma_tilt":
            val = gamma_tilt
        elif key == "put_call_oi_ratio":
            val = put_call_oi_ratio
        elif key == "dollar_put_call_oi_ratio":
            if dollar_call_oi <= 0.0:
                continue
            val = dollar_put_call_oi_ratio
        else:
            val = net_delta
        lo, hi = config.ranges[key]
        score += (normalize(val, lo, hi) - 0.5) * weight
    return score


def compute_signal_agreement(
    positioning: list[dict[str, Any]],
    flow: list[dict[str, Any]],
    gamma: list[dict[str, Any]],
) -> SignalAgreement:
    rows = [*positioning, *flow, *gamma]
    bull = sum(1 for r in rows if r.get("direction") == "bullish")
    bear = sum(1 for r in rows if r.get("direction") == "bearish")
    if bull == bear or bull + bear == 0:
        return "mixed"
    dom_bull = bull > bear
    frac = max(bull, bear) / (bull + bear)
    if frac >= 0.75:
        strength = "strong"
    elif frac >= 0.58:
        strength = "moderate"
    else:
        strength = "weak"
    if dom_bull:
        return cast(SignalAgreement, f"{strength}_bullish")
    return cast(SignalAgreement, f"{strength}_bearish")


def apply_window_to_bias_score(score: float, window: str, config: BiasConfig) -> float:
    if window == "mid":
        return score * config.mid_window_damping
    return score


def bias_probabilities(score: float) -> tuple[float, float, float]:
    bullish_probability = sigmoid(score)
    bearish_probability = sigmoid(-score)
    neutral_probability = max(0.0, 1.0 - max(bullish_probability, bearish_probability))
    prob_total = bullish_probability + bearish_probability + neutral_probability
    return (
        bullish_probability / prob_total,
        bearish_probability / prob_total,
        neutral_probability / prob_total,
    )
