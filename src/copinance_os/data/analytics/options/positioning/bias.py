"""Aggregate directional bias score and signal agreement."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Any, Literal, cast

from copinance_os.data.analytics.options.positioning.math import normalize, sigmoid
from copinance_os.domain.models.common.methodology import MethodologyReference, MethodologySpec
from copinance_os.domain.models.options.positioning import SignalAgreement

# Minimum fraction of the six-driver catalog's absolute weight that must have data
# before the score is trusted enough to publish a directional read (see
# PositioningCoverageModel / compute_bias_coverage in compose.py). Calibrated against
# the achievable coverage values for this catalog: full data 1.000, missing the
# dollar-notional P/C ratio 0.837, missing deltas 0.860, missing all greeks 0.698,
# missing greeks and dollar notional 0.535, missing all OI 0.488 — 0.60 cleanly
# separates "no greeks but real OI and flow" from "no greeks and no notional".
MIN_BIAS_COVERAGE = 0.60

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


DriverDirection = Literal["bullish", "bearish", "neutral"]


@dataclass(frozen=True, slots=True)
class BiasDriver:
    """One weighted signal's contribution to the bias score, applied or not.

    ``contribution`` is in raw signed-weight (log-odds) units — ``centered *
    weight_raw`` — because ``bias_probabilities`` feeds the summed score into a raw
    ``sigmoid`` with implicit slope 1.0. ``weight_share`` is a separate display-only
    field; multiplying it into ``contribution`` would change the sigmoid input and
    silently shift the model (see ``compute_bias_drivers``).
    """

    key: str
    value: float | None
    normalized: float | None
    centered: float | None
    weight_raw: float
    weight_share: float
    contribution: float
    range_low: float
    range_high: float
    applied: bool
    direction: DriverDirection


@dataclass(frozen=True, slots=True)
class BiasBreakdown:
    score: float
    drivers: tuple[BiasDriver, ...]
    applied_weight_total: float


def _driver_direction(contribution: float) -> DriverDirection:
    if contribution > 0.0:
        return "bullish"
    if contribution < 0.0:
        return "bearish"
    return "neutral"


def compute_bias_drivers(
    call_oi_ratio: float | None,
    call_flow_share: float | None,
    gamma_tilt: float | None,
    put_call_oi_ratio: float | None,
    dollar_put_call_oi_ratio: float | None,
    net_delta: float | None,
    dollar_call_oi: float,
    config: BiasConfig = DEFAULT_BIAS_CONFIG,
) -> BiasBreakdown:
    """Per-driver breakdown of the weighted sigmoid-input bias score.

    ``put_call_oi_ratio`` and ``dollar_put_call_oi_ratio`` measure the same skew;
    only one may vote, preferring the dollar-notional variant when it was
    computable (mirrors ``_collapse_duplicate_ratio_vote``'s preference for the
    display/agreement tally). A driver that is ``None`` (not computable from the
    chain) or collapsed as a duplicate is marked ``applied=False`` with a zero
    contribution rather than fabricated.
    """
    use_dollar_ratio = dollar_call_oi > 0.0
    raw: list[BiasDriver] = []
    for key, weight in config.weights.items():
        if key == "call_oi_ratio":
            val = call_oi_ratio
        elif key == "call_flow_share":
            val = call_flow_share
        elif key == "gamma_tilt":
            val = gamma_tilt
        elif key == "put_call_oi_ratio":
            val = None if use_dollar_ratio else put_call_oi_ratio
        elif key == "dollar_put_call_oi_ratio":
            val = dollar_put_call_oi_ratio if use_dollar_ratio else None
        else:
            val = net_delta

        lo, hi = config.ranges[key]
        if val is None:
            raw.append(
                BiasDriver(
                    key=key,
                    value=None,
                    normalized=None,
                    centered=None,
                    weight_raw=weight,
                    weight_share=0.0,
                    contribution=0.0,
                    range_low=lo,
                    range_high=hi,
                    applied=False,
                    direction="neutral",
                )
            )
            continue

        normalized = normalize(val, lo, hi)
        centered = normalized - 0.5
        contribution = centered * weight
        raw.append(
            BiasDriver(
                key=key,
                value=val,
                normalized=normalized,
                centered=centered,
                weight_raw=weight,
                weight_share=0.0,
                contribution=contribution,
                range_low=lo,
                range_high=hi,
                applied=True,
                direction=_driver_direction(contribution),
            )
        )

    # Normalise across applied drivers only, by absolute weight — per-category or
    # signed normalisation would misrepresent a single driver's true share of the
    # vote (see the positioning-matrix redesign plan, Stage 1b).
    applied_weight_total = sum(abs(d.weight_raw) for d in raw if d.applied)
    shared = [
        (
            replace(d, weight_share=abs(d.weight_raw) / applied_weight_total)
            if d.applied and applied_weight_total > 0.0
            else d
        )
        for d in raw
    ]

    score = sum(d.contribution for d in shared)

    # Round displayed contributions to 6dp, folding the residual into the first
    # applied driver so the bars sum exactly to the reported (unrounded) score —
    # mirrors apps/backend/app/services/decision/combine.py's apply_weights.
    rounded = [round(d.contribution, 6) for d in shared]
    residual = round(score - sum(rounded), 6)
    first_applied = next((i for i, d in enumerate(shared) if d.applied), None)
    if first_applied is not None and residual != 0.0:
        rounded[first_applied] = round(rounded[first_applied] + residual, 6)

    drivers = tuple(replace(d, contribution=rounded[i]) for i, d in enumerate(shared))
    return BiasBreakdown(score=score, drivers=drivers, applied_weight_total=applied_weight_total)


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
    return compute_bias_drivers(
        call_oi_ratio,
        call_flow_share,
        gamma_tilt,
        put_call_oi_ratio,
        dollar_put_call_oi_ratio,
        net_delta,
        dollar_call_oi,
        config,
    ).score


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
