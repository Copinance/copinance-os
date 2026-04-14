"""OI-weighted delta exposure (DEX-style aggregate)."""

from __future__ import annotations

from dataclasses import dataclass

from copinance_os.data.analytics.options.positioning.contracts import contract_oi, numeric_greek
from copinance_os.domain.models.market import OptionContract
from copinance_os.domain.models.methodology import MethodologySpec

# OCC-listed equity options use a 100-share multiplier per contract.
DEFAULT_CONTRACT_MULTIPLIER = 100.0


@dataclass(frozen=True, slots=True)
class DeltaConfig:
    contract_multiplier: float = DEFAULT_CONTRACT_MULTIPLIER


DEFAULT_DELTA_CONFIG = DeltaConfig()


def delta_methodology(config: DeltaConfig) -> MethodologySpec:
    return MethodologySpec(
        id="options.positioning.delta_exposure",
        version="v1",
        model_family="oi_weighted_delta_shares",
        assumptions=("Delta taken from vendor or BSM-enriched ``OptionGreeks``.",),
        limitations=("Net delta is a notional exposure snapshot, not a hedge recommendation.",),
        references=(),
        parameters={"contract_multiplier": str(config.contract_multiplier)},
    )


def compute_delta_exposure(
    calls: list[OptionContract],
    puts: list[OptionContract],
    underlying: float,
    config: DeltaConfig = DEFAULT_DELTA_CONFIG,
) -> dict[str, float]:
    m = config.contract_multiplier
    call_dex = 0.0
    for c in calls:
        delta = numeric_greek(c, "delta")
        oi = contract_oi(c)
        if delta is None or oi is None or oi <= 0:
            continue
        call_dex += delta * float(oi) * m
    put_dex = 0.0
    for p in puts:
        delta = numeric_greek(p, "delta")
        oi = contract_oi(p)
        if delta is None or oi is None or oi <= 0:
            continue
        put_dex += delta * float(oi) * m
    net_delta = call_dex + put_dex
    return {
        "net_delta": net_delta,
        "dollar_delta": net_delta * underlying,
        "call_delta_exposure": call_dex,
        "put_delta_exposure": put_dex,
    }
