"""Dollar-weighted OI and volume aggregates."""

from __future__ import annotations

from dataclasses import dataclass

from copinance_os.data.analytics.options.positioning.contracts import (
    contract_mid_price,
    contract_oi,
    contract_vol,
)
from copinance_os.domain.models.market import OptionContract
from copinance_os.domain.models.methodology import MethodologySpec


@dataclass(frozen=True, slots=True)
class DollarConfig:
    pass


DEFAULT_DOLLAR_CONFIG = DollarConfig()


def dollar_methodology(_config: DollarConfig) -> MethodologySpec:
    return MethodologySpec(
        id="options.positioning.dollar_metrics",
        version="v1",
        model_family="mid_times_leg_oi_volume",
        assumptions=("100 multiplier per standard equity option contract.",),
        limitations=("Mids can be stale; wide spreads distort dollar notionals.",),
        references=(),
        parameters={},
    )


def compute_dollar_metrics(
    calls: list[OptionContract],
    puts: list[OptionContract],
    _config: DollarConfig = DEFAULT_DOLLAR_CONFIG,
) -> dict[str, float]:
    dollar_call_oi = 0.0
    dollar_put_oi = 0.0
    dollar_call_vol = 0.0
    dollar_put_vol = 0.0
    for c in calls:
        oi = contract_oi(c)
        vol = contract_vol(c)
        mid = contract_mid_price(c)
        if oi is not None and oi > 0:
            dollar_call_oi += mid * float(oi) * 100.0
        if vol is not None and vol > 0:
            dollar_call_vol += mid * float(vol) * 100.0
    for p in puts:
        oi = contract_oi(p)
        vol = contract_vol(p)
        mid = contract_mid_price(p)
        if oi is not None and oi > 0:
            dollar_put_oi += mid * float(oi) * 100.0
        if vol is not None and vol > 0:
            dollar_put_vol += mid * float(vol) * 100.0
    tot_dollar_vol = dollar_call_vol + dollar_put_vol
    return {
        "dollar_call_oi": dollar_call_oi,
        "dollar_put_oi": dollar_put_oi,
        "dollar_put_call_oi_ratio": dollar_put_oi / max(1.0, dollar_call_oi),
        "dollar_call_volume": dollar_call_vol,
        "dollar_put_volume": dollar_put_vol,
        "dollar_call_flow_share": (
            dollar_call_vol / max(1.0, tot_dollar_vol) if tot_dollar_vol > 0 else 0.0
        ),
    }
