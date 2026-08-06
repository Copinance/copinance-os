"""Aggregate directional bias score and signal agreement."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, cast

from copinance_os.data.analytics.options.positioning.math import normalize, sigmoid
from copinance_os.domain.models.common.methodology import MethodologyReference, MethodologySpec
from copinance_os.domain.models.options.positioning import SignalAgreement

REF_BOLLEN_WHALEY_2004 = MethodologyReference(
    id="REF_BOLLEN_WHALEY_2004",
    title="Bollen, N. P. B., & Whaley, R. E. (2004), Does net buying pressure affect the shape of implied volatility functions?, Journal of Finance, 59(2), 711-753",
    url="https://doi.org/10.1111/j.1540-6261.2004.00663.x",
)
REF_PAN_POTESHMAN_2006 = MethodologyReference(
    id="REF_PAN_POTESHMAN_2006",
    title="Pan, J., & Poteshman, A. M. (2006), The information in option volume for future stock prices, Review of Financial Studies, 19(3), 871-908",
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


DEFAULT_BIAS_CONFIG = BiasConfig()


def bias_methodology(config: BiasConfig) -> MethodologySpec:
    return MethodologySpec(
        id="options.positioning.bias",
        version="v2",
        model_family="weighted_sigmoid_bias",
        assumptions=("Fixed transparent weights across OI/flow/Greek tilts.",),
        limitations=("Heuristic; not execution advice.",),
        references=(REF_BOLLEN_WHALEY_2004, REF_PAN_POTESHMAN_2006),
        parameters={
            "weights": str(dict(config.weights)),
            "ranges": str(dict(config.ranges)),
        },
    )


def compute_bias_score(
    call_oi_ratio: float | None,
    call_flow_share: float | None,
    gamma_tilt: float | None,
    put_call_oi_ratio: float | None,
    dollar_put_call_oi_ratio: float | None,
    net_delta: float | None,
    dollar_call_oi: float,
    config: BiasConfig = DEFAULT_BIAS_CONFIG,
) -> float:
    """Weighted sigmoid-input score over the six directional drivers.

    ``put_call_oi_ratio`` and ``dollar_put_call_oi_ratio`` measure the same skew;
    only one may vote, preferring the dollar-notional variant when it was
    computable (mirrors ``_collapse_duplicate_ratio_vote``'s preference for the
    display/agreement tally). Any driver that is ``None`` (not computable from the
    chain) is skipped rather than fabricated.
    """
    score = 0.0
    use_dollar_ratio = dollar_call_oi > 0.0
    for key, weight in config.weights.items():
        if key == "call_oi_ratio":
            val = call_oi_ratio
        elif key == "call_flow_share":
            val = call_flow_share
        elif key == "gamma_tilt":
            val = gamma_tilt
        elif key == "put_call_oi_ratio":
            if use_dollar_ratio:
                continue
            val = put_call_oi_ratio
        elif key == "dollar_put_call_oi_ratio":
            if not use_dollar_ratio:
                continue
            val = dollar_put_call_oi_ratio
        else:
            val = net_delta
        if val is None:
            continue
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


def signal_agreement_direction(agreement: str) -> str:
    """Map a :data:`SignalAgreement` value to a tri-state direction string.

    Returns ``"bullish"``, ``"bearish"``, or ``"neutral"`` (for ``"mixed"``).
    Consumers use this when they need a simple directional chip rather than the
    full agreement strength (e.g. sector treemap options-flow indicators).
    """
    if "bullish" in agreement:
        return "bullish"
    if "bearish" in agreement:
        return "bearish"
    return "neutral"


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
