"""Vanna exposure (front-expiry OI-weighted)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from copinance_os.data.analytics.options.positioning.contracts import (
    contract_oi,
    contract_strike,
    contracts_for_expiration,
    numeric_greek,
)
from copinance_os.domain.models.market import OptionContract
from copinance_os.domain.models.methodology import MethodologySpec

# Floor prevents unstable tiny-sample regime flips.
DEFAULT_VANNA_REGIME_FLOOR = 5000.0
# Relative threshold scales with gross OI-weighted vanna.
DEFAULT_VANNA_REGIME_GROSS_FRACTION = 0.03
# Keep only the most material strike exposures in output.
DEFAULT_VANNA_PROFILE_TOP_K = 15


@dataclass(frozen=True, slots=True)
class VannaConfig:
    vanna_regime_floor: float = DEFAULT_VANNA_REGIME_FLOOR
    vanna_regime_gross_frac: float = DEFAULT_VANNA_REGIME_GROSS_FRACTION
    profile_top_k: int = DEFAULT_VANNA_PROFILE_TOP_K


DEFAULT_VANNA_CONFIG = VannaConfig()


def vanna_methodology(config: VannaConfig) -> MethodologySpec:
    return MethodologySpec(
        id="options.positioning.vanna",
        version="v1",
        model_family="oi_weighted_vanna_surface",
        assumptions=("Call minus put vanna at nearest expiry; flip via cumulative strike ladder.",),
        limitations=("Public chain vanna is model-dependent (BSM here).",),
        references=(),
        parameters={
            "vanna_regime_floor": str(config.vanna_regime_floor),
            "vanna_regime_gross_frac": str(config.vanna_regime_gross_frac),
        },
    )


def _vanna_strike_multiplier(underlying: float) -> float:
    return 100.0 * max(underlying, 1e-9)


def _vanna_regime_threshold(
    calls: list[OptionContract], puts: list[OptionContract], config: VannaConfig
) -> float:
    gross = 0.0
    for c in calls:
        vanna = numeric_greek(c, "vanna")
        oi = contract_oi(c)
        if vanna is None or oi is None or oi <= 0:
            continue
        gross += abs(vanna) * float(oi)
    for p in puts:
        vanna = numeric_greek(p, "vanna")
        oi = contract_oi(p)
        if vanna is None or oi is None or oi <= 0:
            continue
        gross += abs(vanna) * float(oi)
    return max(config.vanna_regime_floor, config.vanna_regime_gross_frac * gross * 100.0)


def compute_vanna_exposure(
    calls: list[OptionContract],
    puts: list[OptionContract],
    nearest_exp: str | None,
    underlying: float,
    config: VannaConfig = DEFAULT_VANNA_CONFIG,
) -> dict[str, Any]:
    if not nearest_exp or underlying <= 0:
        return {"vanna_exposure": None, "vanna_profile": []}
    mult = _vanna_strike_multiplier(underlying)
    strike_to_net: dict[float, float] = defaultdict(float)
    call_sum = 0.0
    put_sum = 0.0
    for c in contracts_for_expiration(calls, nearest_exp):
        v = numeric_greek(c, "vanna")
        oi = contract_oi(c)
        if v is None or oi is None or oi <= 0:
            continue
        strike_to_net[contract_strike(c)] += v * float(oi) * mult
        call_sum += v * float(oi) * 100.0
    for p in contracts_for_expiration(puts, nearest_exp):
        v = numeric_greek(p, "vanna")
        oi = contract_oi(p)
        if v is None or oi is None or oi <= 0:
            continue
        strike_to_net[contract_strike(p)] -= v * float(oi) * mult
        put_sum += v * float(oi) * 100.0

    if not strike_to_net or not any(abs(v) > 1e-9 for v in strike_to_net.values()):
        net_plain = call_sum - put_sum
        thr = _vanna_regime_threshold(
            contracts_for_expiration(calls, nearest_exp),
            contracts_for_expiration(puts, nearest_exp),
            config,
        )
        regime = (
            "short_vanna" if net_plain < -thr else "long_vanna" if net_plain > thr else "neutral"
        )
        return {
            "vanna_exposure": {
                "net_vanna": round(net_plain, 4),
                "call_vanna_exposure": round(call_sum, 4),
                "put_vanna_exposure": round(put_sum, 4),
                "vanna_flip_strike": None,
                "regime": regime,
            },
            "vanna_profile": [],
        }

    strikes_sorted = sorted(strike_to_net.keys())
    per_strike = [(k, strike_to_net[k]) for k in strikes_sorted]

    vanna_flip: float | None = None
    cumulative = 0.0
    for i, (k, vx_k) in enumerate(per_strike):
        next_cum = cumulative + vx_k
        if i > 0 and cumulative * next_cum < 0.0:
            k_prev, _ = per_strike[i - 1]
            span = next_cum - cumulative
            t = abs(cumulative) / max(1e-12, abs(span))
            vanna_flip = k_prev + t * (k - k_prev)
            break
        cumulative = next_cum

    ranked_abs = sorted(per_strike, key=lambda kv: abs(kv[1]), reverse=True)
    profile_cap = ranked_abs[: config.profile_top_k]
    vanna_profile = [{"strike": float(k), "vanna_exposure": round(v, 4)} for k, v in profile_cap]

    net_plain = call_sum - put_sum
    c_near = contracts_for_expiration(calls, nearest_exp)
    p_near = contracts_for_expiration(puts, nearest_exp)
    thr = _vanna_regime_threshold(c_near, p_near, config)
    regime = "short_vanna" if net_plain < -thr else "long_vanna" if net_plain > thr else "neutral"

    return {
        "vanna_exposure": {
            "net_vanna": round(net_plain, 4),
            "call_vanna_exposure": round(call_sum, 4),
            "put_vanna_exposure": round(put_sum, 4),
            "vanna_flip_strike": round(vanna_flip, 4) if vanna_flip is not None else None,
            "regime": regime,
        },
        "vanna_profile": vanna_profile,
    }
