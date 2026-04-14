"""Mid vs BSM theoretical price (mispricing) aggregates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from copinance_os.data.analytics.options.positioning.contracts import contract_mid_price
from copinance_os.domain.models.market import OptionContract
from copinance_os.domain.models.methodology import MethodologySpec


@dataclass(frozen=True, slots=True)
class MispricingConfig:
    demand_threshold_pct: float = 2.0
    peer_cap_pct: float = 1.0


DEFAULT_MISPRICING_CONFIG = MispricingConfig()


def mispricing_methodology(config: MispricingConfig) -> MethodologySpec:
    return MethodologySpec(
        id="options.positioning.mispricing",
        version="v1",
        model_family="mid_vs_bsm_npv",
        assumptions=("Uses ``greeks.theoretical_price`` when present.",),
        limitations=("Ignores borrow, discrete dividends, and microstructure beyond mid.",),
        references=(),
        parameters={
            "demand_threshold_pct": str(config.demand_threshold_pct),
            "peer_cap_pct": str(config.peer_cap_pct),
        },
    )


def compute_mispricing(
    calls: list[OptionContract],
    puts: list[OptionContract],
    config: MispricingConfig = DEFAULT_MISPRICING_CONFIG,
) -> dict[str, Any] | None:
    call_pcts: list[float] = []
    put_pcts: list[float] = []
    call_over = 0
    call_n = 0
    put_over = 0
    put_n = 0

    for contract in calls:
        g = contract.greeks
        if g is None or g.theoretical_price is None:
            continue
        theo = float(g.theoretical_price)
        if theo <= 0:
            continue
        mid = contract_mid_price(contract)
        if mid <= 0:
            continue
        pct = (mid - theo) / max(0.01, theo) * 100.0
        call_pcts.append(pct)
        call_n += 1
        if mid > theo:
            call_over += 1

    for contract in puts:
        g = contract.greeks
        if g is None or g.theoretical_price is None:
            continue
        theo = float(g.theoretical_price)
        if theo <= 0:
            continue
        mid = contract_mid_price(contract)
        if mid <= 0:
            continue
        pct = (mid - theo) / max(0.01, theo) * 100.0
        put_pcts.append(pct)
        put_n += 1
        if mid > theo:
            put_over += 1

    if not call_pcts and not put_pcts:
        return None

    call_avg = sum(call_pcts) / len(call_pcts) if call_pcts else 0.0
    put_avg = sum(put_pcts) / len(put_pcts) if put_pcts else 0.0
    sentiment = "neutral"
    if call_avg > config.demand_threshold_pct and put_avg < config.peer_cap_pct:
        sentiment = "call_demand"
    elif put_avg > config.demand_threshold_pct and call_avg < config.peer_cap_pct:
        sentiment = "put_demand"

    return {
        "mispricing": {
            "call_avg_mispricing_pct": round(call_avg, 4),
            "put_avg_mispricing_pct": round(put_avg, 4),
            "overpriced_call_pct": round(call_over / max(1, call_n), 4),
            "overpriced_put_pct": round(put_over / max(1, put_n), 4),
            "sentiment": sentiment,
        }
    }
