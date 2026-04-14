"""ATM straddle implied move (Brenner–Subrahmanyam-style annualisation)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Any

from copinance_os.data.analytics.options.positioning.contracts import (
    atm_strike,
    contract_bid_ask,
    contract_oi,
    contract_strike,
    contract_vol,
    contracts_for_expiration,
    parse_expiration_to_date,
)
from copinance_os.domain.models.market import OptionContract
from copinance_os.domain.models.methodology import MethodologySpec


@dataclass(frozen=True, slots=True)
class ImpliedMoveConfig:
    straddle_ann_factor: float = 0.798
    trading_days_per_year: float = 252.0


DEFAULT_IMPLIED_MOVE_CONFIG = ImpliedMoveConfig()


def implied_move_methodology(config: ImpliedMoveConfig) -> MethodologySpec:
    return MethodologySpec(
        id="options.positioning.implied_move",
        version="v1",
        model_family="atm_straddle_brenner_subrahmanyam",
        assumptions=("European-style straddle on matched ATM call/put mids.",),
        limitations=("Ignores skew/smile beyond the chosen ATM pair.",),
        references=(),
        parameters={
            "straddle_ann_factor": str(config.straddle_ann_factor),
            "trading_days_per_year": str(config.trading_days_per_year),
        },
    )


def compute_implied_move(
    calls: list[OptionContract],
    puts: list[OptionContract],
    nearest_exp: str | None,
    underlying: float,
    as_of_date: date,
    config: ImpliedMoveConfig = DEFAULT_IMPLIED_MOVE_CONFIG,
) -> tuple[float, float, dict[str, Any] | None]:
    if not nearest_exp or underlying <= 0:
        return 0.0, 0.0, None
    c_near = contracts_for_expiration(calls, nearest_exp)
    p_near = contracts_for_expiration(puts, nearest_exp)
    strikes = sorted(
        {contract_strike(c) for c in c_near if (contract_oi(c) or 0) + (contract_vol(c) or 0) > 0}
        & {contract_strike(p) for p in p_near if (contract_oi(p) or 0) + (contract_vol(p) or 0) > 0}
    )
    atm = atm_strike(strikes, underlying)
    if atm is None:
        return 0.0, 0.0, None
    call_mid = 0.0
    put_mid = 0.0
    found_c = found_p = False
    for c in c_near:
        if abs(contract_strike(c) - atm) < 1e-6:
            bid, ask = contract_bid_ask(c)
            if bid > 0 or ask > 0:
                call_mid = (bid + ask) / 2.0 if ask >= bid else max(bid, ask)
                found_c = True
                break
    for p in p_near:
        if abs(contract_strike(p) - atm) < 1e-6:
            bid, ask = contract_bid_ask(p)
            if bid > 0 or ask > 0:
                put_mid = (bid + ask) / 2.0 if ask >= bid else max(bid, ask)
                found_p = True
                break
    if not (found_c and found_p):
        return 0.0, 0.0, None
    straddle = call_mid + put_mid
    pct = (straddle / underlying) * 100.0
    exp_d = parse_expiration_to_date(nearest_exp)
    if exp_d is None:
        return round(pct, 4), round(straddle, 4), None
    dte = max(1, (exp_d - as_of_date).days)
    t_year = dte / 365.0
    fac = config.straddle_ann_factor
    td = config.trading_days_per_year
    ann = (straddle / (fac * underlying * math.sqrt(t_year))) * 100.0
    daily = ann / math.sqrt(td)
    period = ann * math.sqrt(dte / td)
    detail = {
        "raw_straddle_pct": round(pct, 4),
        "raw_straddle_abs": round(straddle, 4),
        "dte": dte,
        "annualized_iv": round(ann, 4),
        "daily_implied_move_pct": round(daily, 4),
        "period_implied_move_pct": round(period, 4),
    }
    return round(pct, 4), round(straddle, 4), detail
