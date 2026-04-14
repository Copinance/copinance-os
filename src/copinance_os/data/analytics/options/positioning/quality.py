"""Chain data-quality score (coverage, spreads, depth)."""

from __future__ import annotations

from dataclasses import dataclass

from copinance_os.data.analytics.options.positioning.contracts import (
    contract_bid_ask,
    contract_iv_pct,
    contract_oi,
    contract_strike,
    contract_vol,
)
from copinance_os.domain.models.market import OptionContract
from copinance_os.domain.models.methodology import MethodologySpec


@dataclass(frozen=True, slots=True)
class DataQualityConfig:
    weight_greeks: float = 0.30
    weight_iv: float = 0.20
    weight_spread: float = 0.20
    weight_oi: float = 0.15
    weight_strike_breadth: float = 0.15
    oi_depth_scale: float = 10_000.0
    strike_breadth_scale: float = 20.0


DEFAULT_DATA_QUALITY_CONFIG = DataQualityConfig()


def data_quality_methodology(config: DataQualityConfig) -> MethodologySpec:
    return MethodologySpec(
        id="options.positioning.data_quality",
        version="v1",
        model_family="coverage_and_microstructure_composite",
        assumptions=("Weights sum to 1.0; each sub-score in [0,1].",),
        limitations=("Heuristic blend; not a liquidity guarantee.",),
        references=(),
        parameters={
            "weight_greeks": str(config.weight_greeks),
            "weight_iv": str(config.weight_iv),
            "weight_spread": str(config.weight_spread),
            "weight_oi": str(config.weight_oi),
            "weight_strike_breadth": str(config.weight_strike_breadth),
        },
    )


def compute_data_quality(
    calls: list[OptionContract],
    puts: list[OptionContract],
    underlying: float,
    config: DataQualityConfig = DEFAULT_DATA_QUALITY_CONFIG,
) -> float:
    contracts = [*calls, *puts]
    if not contracts:
        return 0.0
    n = len(contracts)
    greeks_ok = sum(1 for c in contracts if c.greeks is not None)
    greeks_coverage = greeks_ok / n
    iv_ok = sum(1 for c in contracts if contract_iv_pct(c) > 0)
    iv_coverage = iv_ok / n

    tight_vals: list[float] = []
    for c in contracts:
        bid, ask = contract_bid_ask(c)
        mid = (bid + ask) / 2.0 if ask >= bid and (bid > 0 or ask > 0) else 0.0
        if mid > 0:
            spread_ratio = (ask - bid) / mid
            tight_vals.append(max(0.0, min(1.0, 1.0 - spread_ratio)))
    spread_tightness = sum(tight_vals) / len(tight_vals) if tight_vals else 0.0

    total_oi = sum(contract_oi(c) for c in contracts)
    oi_depth = min(1.0, total_oi / max(1e-12, config.oi_depth_scale))

    active_strikes = len(
        {
            round(contract_strike(c), 6)
            for c in contracts
            if contract_oi(c) > 0 or contract_vol(c) > 0
        }
    )
    strike_breadth = min(1.0, active_strikes / max(1e-12, config.strike_breadth_scale))

    return float(
        config.weight_greeks * greeks_coverage
        + config.weight_iv * iv_coverage
        + config.weight_spread * spread_tightness
        + config.weight_oi * oi_depth
        + config.weight_strike_breadth * strike_breadth
    )
