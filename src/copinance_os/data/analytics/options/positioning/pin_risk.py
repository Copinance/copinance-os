"""Short-dated pin-risk heuristic (OI × P(ITM))."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any

from copinance_os.data.analytics.options.positioning.contracts import (
    contract_oi,
    contract_strike,
    contract_vol,
    contracts_for_expiration,
    parse_expiration_to_date,
)
from copinance_os.domain.models.market import OptionContract
from copinance_os.domain.models.methodology import MethodologySpec


@dataclass(frozen=True, slots=True)
class PinRiskConfig:
    max_dte: int = 5
    min_total_oi: int = 1000
    pin_score_flow_mult: float = 6.0
    pin_score_distance_mult: float = 4.0
    high_score: float = 0.7
    moderate_score: float = 0.4
    high_dte: int = 2
    moderate_dte: int = 5


DEFAULT_PIN_RISK_CONFIG = PinRiskConfig()


def pin_risk_methodology(config: PinRiskConfig) -> MethodologySpec:
    return MethodologySpec(
        id="options.positioning.pin_risk",
        version="v1",
        model_family="short_dated_oi_times_itm_probability",
        assumptions=("Uses ``greeks.itm_probability`` when populated.",),
        limitations=("Exercise dynamics and borrow are not modeled.",),
        references=(),
        parameters={"max_dte": str(config.max_dte), "min_total_oi": str(config.min_total_oi)},
    )


def compute_pin_risk(
    calls: list[OptionContract],
    puts: list[OptionContract],
    nearest_exp: str | None,
    underlying: float,
    as_of_date: date,
    config: PinRiskConfig = DEFAULT_PIN_RISK_CONFIG,
) -> dict[str, Any] | None:
    if not nearest_exp or underlying <= 0:
        return None
    exp_d = parse_expiration_to_date(nearest_exp)
    if exp_d is None:
        return None
    dte = (exp_d - as_of_date).days
    if dte > config.max_dte:
        return None

    total_vol = sum(contract_vol(c) or 0 for c in calls) + sum(contract_vol(p) or 0 for p in puts)

    calls_by_k: dict[float, list[OptionContract]] = defaultdict(list)
    puts_by_k: dict[float, list[OptionContract]] = defaultdict(list)
    for c in contracts_for_expiration(calls, nearest_exp):
        calls_by_k[contract_strike(c)].append(c)
    for p in contracts_for_expiration(puts, nearest_exp):
        puts_by_k[contract_strike(p)].append(p)

    def _weighted_itm(contracts: list[OptionContract]) -> float | None:
        num = 0.0
        den = 0
        for c in contracts:
            if c.greeks is None or c.greeks.itm_probability is None:
                continue
            oi = contract_oi(c)
            if oi is None or oi <= 0:
                continue
            num += float(c.greeks.itm_probability) * oi
            den += oi
        if den <= 0:
            return None
        return num / den

    strikes_set = set(calls_by_k.keys()) | set(puts_by_k.keys())
    rows: list[tuple[float, int, float, float]] = []
    for k in strikes_set:
        call_oi = sum(
            oi for c in calls_by_k.get(k, ()) if (oi := contract_oi(c)) is not None and oi > 0
        )
        put_oi = sum(
            oi for p in puts_by_k.get(k, ()) if (oi := contract_oi(p)) is not None and oi > 0
        )
        total_oi = call_oi + put_oi
        if total_oi <= config.min_total_oi:
            continue
        pc = _weighted_itm(calls_by_k.get(k, []))
        pp = _weighted_itm(puts_by_k.get(k, []))
        expected = 0.0
        if pc is not None:
            expected += call_oi * pc
        if pp is not None:
            expected += put_oi * pp
        if expected <= 0 and pc is None and pp is None:
            continue
        rel = abs(k - underlying) / max(underlying, 1e-9)
        flow_ratio = expected / max(1.0, float(total_vol))
        pin_score = min(1.0, flow_ratio * config.pin_score_flow_mult) * (
            1.0 / (1.0 + config.pin_score_distance_mult * rel)
        )
        rows.append((k, total_oi, expected, pin_score))

    if not rows:
        level = "low"
        return {
            "max_pin_strike": None,
            "pin_risk_level": level,
            "dte": dte,
            "top_strikes": [],
        }

    max_row = max(rows, key=lambda r: r[3])
    max_pin_strike = float(max_row[0])
    max_score = float(max_row[3])
    if dte <= config.high_dte and max_score > config.high_score:
        level = "high"
    elif dte <= config.moderate_dte and max_score > config.moderate_score:
        level = "moderate"
    else:
        level = "low"

    top = sorted(rows, key=lambda r: r[3], reverse=True)[:5]
    top_strikes = [
        {
            "strike": float(k),
            "total_oi": int(tot),
            "expected_exercised": round(ex, 4),
            "pin_score": round(sc, 4),
        }
        for k, tot, ex, sc in top
    ]

    return {
        "max_pin_strike": round(max_pin_strike, 4),
        "pin_risk_level": level,
        "dte": dte,
        "top_strikes": top_strikes,
    }
