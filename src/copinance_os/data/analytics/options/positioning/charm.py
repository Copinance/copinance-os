"""Charm exposure (OI-weighted ∂Δ/∂τ)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from copinance_os.data.analytics.options.positioning.contracts import contract_oi, numeric_greek
from copinance_os.domain.models.market import OptionContract
from copinance_os.domain.models.methodology import MethodologySpec


@dataclass(frozen=True, slots=True)
class CharmConfig:
    drift_gross_frac: float = 0.02
    drift_floor: float = 1e-6


DEFAULT_CHARM_CONFIG = CharmConfig()


def charm_methodology(config: CharmConfig) -> MethodologySpec:
    return MethodologySpec(
        id="options.positioning.charm",
        version="v1",
        model_family="oi_weighted_charm_aggregate",
        assumptions=("Calendar-time charm from BSM when ``greeks.charm`` is populated.",),
        limitations=("Overnight drift label is a coarse heuristic vs path-dependent reality.",),
        references=(),
        parameters={
            "drift_gross_frac": str(config.drift_gross_frac),
            "drift_floor": str(config.drift_floor),
        },
    )


def _charm_drift_threshold(
    calls: list[OptionContract], puts: list[OptionContract], config: CharmConfig
) -> float:
    gross = 0.0
    for c in calls:
        charm = numeric_greek(c, "charm")
        oi = contract_oi(c)
        if charm is None or oi is None or oi <= 0:
            continue
        gross += abs(charm) * float(oi)
    for p in puts:
        charm = numeric_greek(p, "charm")
        oi = contract_oi(p)
        if charm is None or oi is None or oi <= 0:
            continue
        gross += abs(charm) * float(oi)
    return max(config.drift_floor, config.drift_gross_frac * gross * 100.0)


def compute_charm_exposure(
    calls: list[OptionContract],
    puts: list[OptionContract],
    config: CharmConfig = DEFAULT_CHARM_CONFIG,
) -> dict[str, Any]:
    call_sum = 0.0
    for c in calls:
        charm = numeric_greek(c, "charm")
        oi = contract_oi(c)
        if charm is None or oi is None or oi <= 0:
            continue
        call_sum += charm * float(oi) * 100.0
    put_sum = 0.0
    for p in puts:
        charm = numeric_greek(p, "charm")
        oi = contract_oi(p)
        if charm is None or oi is None or oi <= 0:
            continue
        put_sum += charm * float(oi) * 100.0
    net_charm = call_sum + put_sum
    thr = _charm_drift_threshold(calls, puts, config)
    if net_charm > thr:
        drift = "selling_pressure"
    elif net_charm < -thr:
        drift = "buying_pressure"
    else:
        drift = "neutral"
    return {
        "charm_exposure": {
            "net_charm": round(net_charm, 4),
            "call_charm_exposure": round(call_sum, 4),
            "put_charm_exposure": round(put_sum, 4),
            "overnight_delta_drift": drift,
        }
    }
