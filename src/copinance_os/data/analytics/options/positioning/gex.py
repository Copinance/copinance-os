"""Gamma exposure (GEX) profile and aggregate gamma regime."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Literal

from copinance_os.data.analytics.options.positioning.contracts import (
    contract_oi,
    contract_strike,
    contracts_for_expiration,
    numeric_greek,
)
from copinance_os.data.literacy import options_positioning as _pt
from copinance_os.domain.literacy import FinancialLiteracy
from copinance_os.domain.models.market import OptionContract
from copinance_os.domain.models.methodology import MethodologySpec

# Keep only the largest absolute strike contributions for compact reports.
DEFAULT_GEX_PROFILE_TOP_K = 15
DEFAULT_GEX_TOP_POSITIVE_K = 5
DEFAULT_GEX_TOP_NEGATIVE_K = 5
# Relative net/gross gamma threshold for regime assignment.
DEFAULT_GAMMA_REGIME_THRESHOLD = 0.06


@dataclass(frozen=True, slots=True)
class GexConfig:
    profile_top_k: int = DEFAULT_GEX_PROFILE_TOP_K
    top_positive_k: int = DEFAULT_GEX_TOP_POSITIVE_K
    top_negative_k: int = DEFAULT_GEX_TOP_NEGATIVE_K
    gamma_regime_threshold: float = DEFAULT_GAMMA_REGIME_THRESHOLD


DEFAULT_GEX_CONFIG = GexConfig()


def gex_methodology(config: GexConfig) -> MethodologySpec:
    return MethodologySpec(
        id="options.positioning.gex",
        version="v1",
        model_family="dealer_gamma_exposure",
        assumptions=("Nearest listed expiry only; OI-weighted gamma with spot scaling.",),
        limitations=("Dealer positioning is inferred heuristically from public chain data.",),
        references=(),
        parameters={
            "profile_top_k": str(config.profile_top_k),
            "gamma_regime_threshold": str(config.gamma_regime_threshold),
        },
    )


def compute_gex_profile(
    calls: list[OptionContract],
    puts: list[OptionContract],
    nearest_exp: str | None,
    underlying: float,
    config: GexConfig = DEFAULT_GEX_CONFIG,
) -> dict[str, Any]:
    if not nearest_exp or underlying <= 0:
        return {
            "gamma_flip_strike": None,
            "gex_profile": [],
            "top_positive_gex": [],
            "top_negative_gex": [],
        }
    mult = 100.0 * underlying
    strike_to_net: dict[float, float] = defaultdict(float)
    for c in contracts_for_expiration(calls, nearest_exp):
        g = numeric_greek(c, "gamma")
        oi = contract_oi(c)
        if g is None or oi is None or oi <= 0:
            continue
        strike_to_net[contract_strike(c)] += g * float(oi) * mult
    for p in contracts_for_expiration(puts, nearest_exp):
        g = numeric_greek(p, "gamma")
        oi = contract_oi(p)
        if g is None or oi is None or oi <= 0:
            continue
        strike_to_net[contract_strike(p)] -= g * float(oi) * mult

    if not strike_to_net:
        return {
            "gamma_flip_strike": None,
            "gex_profile": [],
            "top_positive_gex": [],
            "top_negative_gex": [],
        }

    if not any(abs(v) > 1e-9 for v in strike_to_net.values()):
        return {
            "gamma_flip_strike": None,
            "gex_profile": [],
            "top_positive_gex": [],
            "top_negative_gex": [],
        }

    strikes_sorted = sorted(strike_to_net.keys())
    per_strike = [(k, strike_to_net[k]) for k in strikes_sorted]

    gamma_flip: float | None = None
    cumulative = 0.0
    for i, (k, gex_k) in enumerate(per_strike):
        next_cum = cumulative + gex_k
        if i > 0 and cumulative * next_cum < 0.0:
            k_prev, _ = per_strike[i - 1]
            span = next_cum - cumulative
            t = abs(cumulative) / max(1e-12, abs(span))
            gamma_flip = k_prev + t * (k - k_prev)
            break
        cumulative = next_cum

    ranked_abs = sorted(per_strike, key=lambda kv: abs(kv[1]), reverse=True)
    profile_cap = ranked_abs[: config.profile_top_k]
    gex_profile = [{"strike": float(k), "gex_value": round(v, 4)} for k, v in profile_cap]

    pos_sorted = sorted((kv for kv in per_strike if kv[1] > 0), key=lambda kv: kv[1], reverse=True)[
        : config.top_positive_k
    ]
    neg_sorted = sorted((kv for kv in per_strike if kv[1] < 0), key=lambda kv: kv[1])[
        : config.top_negative_k
    ]
    top_pos = [{"strike": float(k), "gex_value": round(v, 4)} for k, v in pos_sorted]
    top_neg = [{"strike": float(k), "gex_value": round(v, 4)} for k, v in neg_sorted]

    return {
        "gamma_flip_strike": round(gamma_flip, 4) if gamma_flip is not None else None,
        "gex_profile": gex_profile,
        "top_positive_gex": top_pos,
        "top_negative_gex": top_neg,
    }


def compute_gamma_regime(
    calls: list[OptionContract],
    puts: list[OptionContract],
    underlying: float,
    lit: FinancialLiteracy,
    config: GexConfig = DEFAULT_GEX_CONFIG,
) -> tuple[
    list[dict[str, Any]], float, Literal["positive_gamma", "negative_gamma", "neutral"], str
]:
    net = 0.0
    gross = 0.0
    mult = 100.0 * max(underlying, 1e-9)
    for c in calls:
        g = numeric_greek(c, "gamma")
        oi = contract_oi(c)
        if g is None or oi is None or oi <= 0:
            continue
        contrib = g * oi * mult
        net += contrib
        gross += abs(contrib)
    for p in puts:
        g = numeric_greek(p, "gamma")
        oi = contract_oi(p)
        if g is None or oi is None or oi <= 0:
            continue
        contrib = g * oi * mult
        net -= contrib
        gross += abs(contrib)

    thr = config.gamma_regime_threshold
    if gross < 1e-6:
        regime: Literal["positive_gamma", "negative_gamma", "neutral"] = "neutral"
        expl = _pt.expl_gamma_neutral_flat(lit)
    else:
        rel = net / gross
        if rel > thr:
            regime = "positive_gamma"
            expl = _pt.expl_gamma_positive(lit)
        elif rel < -thr:
            regime = "negative_gamma"
            expl = _pt.expl_gamma_negative(lit)
        else:
            regime = "neutral"
            expl = _pt.expl_gamma_balanced(lit)

    net_rounded = round(net, 4)
    signals = [
        {
            "name": _pt.name_net_gamma(lit),
            "value": net_rounded,
            "direction": "bullish" if net > 0 else "bearish" if net < 0 else "neutral",
            "explanation": _pt.expl_net_gamma(lit),
        },
        {
            "name": _pt.name_gamma_regime(lit),
            "value": (
                1.0 if regime == "positive_gamma" else -1.0 if regime == "negative_gamma" else 0.0
            ),
            "direction": (
                "bullish"
                if regime == "positive_gamma"
                else "bearish" if regime == "negative_gamma" else "neutral"
            ),
            "explanation": expl,
        },
    ]
    return signals, net_rounded, regime, expl
