"""ATM IV and cross-sectional IV rank."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from copinance_os.data.analytics.options.positioning.contracts import (
    atm_strike,
    contract_iv_pct,
    contract_oi,
    contract_strike,
    contract_vol,
    contracts_for_expiration,
)
from copinance_os.data.analytics.options.positioning.math import percentile_rank
from copinance_os.data.literacy import options_positioning as _pt
from copinance_os.domain.literacy import FinancialLiteracy
from copinance_os.domain.models.market import OptionContract
from copinance_os.domain.models.methodology import MethodologySpec


@dataclass(frozen=True, slots=True)
class VolatilityConfig:
    iv_rank_bearish: float = 0.72
    iv_rank_bullish: float = 0.35
    iv_rank_dir_bearish: float = 0.65
    iv_rank_dir_bullish: float = 0.4


DEFAULT_VOLATILITY_CONFIG = VolatilityConfig()


def volatility_methodology(config: VolatilityConfig) -> MethodologySpec:
    return MethodologySpec(
        id="options.positioning.volatility",
        version="v1",
        model_family="atm_iv_and_iv_rank",
        assumptions=("IV rank is empirical percentile within the current chain cross-section.",),
        limitations=("Single-snapshot rank is not a long-horizon implied-vol history.",),
        references=(),
        parameters={
            "iv_rank_bearish": str(config.iv_rank_bearish),
            "iv_rank_bullish": str(config.iv_rank_bullish),
        },
    )


def compute_volatility_signals(
    calls: list[OptionContract],
    puts: list[OptionContract],
    nearest_exp: str | None,
    underlying: float,
    all_iv_samples: list[float],
    lit: FinancialLiteracy,
    config: VolatilityConfig = DEFAULT_VOLATILITY_CONFIG,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not nearest_exp or underlying <= 0:
        return (
            [
                {
                    "name": _pt.name_atm_iv(lit),
                    "value": 0.0,
                    "direction": "neutral",
                    "explanation": _pt.expl_iv_insufficient(lit),
                },
                {
                    "name": _pt.name_iv_rank(lit),
                    "value": 0.5,
                    "direction": "neutral",
                    "explanation": _pt.expl_iv_rank_no_iv(lit),
                },
            ],
            {"atm_iv": 0.0, "iv_rank": 0.5},
        )

    c_near = contracts_for_expiration(calls, nearest_exp)
    p_near = contracts_for_expiration(puts, nearest_exp)
    strikes = sorted(
        {
            contract_strike(x)
            for x in (*c_near, *p_near)
            if contract_oi(x) + contract_vol(x) > 0 and contract_iv_pct(x) > 0
        }
    )
    atm = atm_strike(strikes, underlying)
    if atm is None:
        return (
            [
                {
                    "name": _pt.name_atm_iv(lit),
                    "value": 0.0,
                    "direction": "neutral",
                    "explanation": _pt.expl_iv_no_quotes_near_money(lit),
                },
                {
                    "name": _pt.name_iv_rank(lit),
                    "value": round(percentile_rank(0.0, all_iv_samples), 4),
                    "direction": "neutral",
                    "explanation": _pt.expl_iv_rank_degenerate(lit),
                },
            ],
            {"atm_iv": 0.0, "iv_rank": percentile_rank(0.0, all_iv_samples)},
        )

    atm_ivs: list[float] = []
    for c in c_near:
        if abs(contract_strike(c) - atm) < 1e-6 and contract_iv_pct(c) > 0:
            atm_ivs.append(contract_iv_pct(c))
    for p in p_near:
        if abs(contract_strike(p) - atm) < 1e-6 and contract_iv_pct(p) > 0:
            atm_ivs.append(contract_iv_pct(p))
    atm_iv = sum(atm_ivs) / len(atm_ivs) if atm_ivs else 0.0

    iv_rank = percentile_rank(atm_iv, all_iv_samples) if all_iv_samples else 0.5
    iv_dir: Literal["bullish", "bearish", "neutral"] = (
        "bearish"
        if iv_rank >= config.iv_rank_bearish
        else "bullish" if iv_rank <= config.iv_rank_bullish else "neutral"
    )
    rank_dir: Literal["bullish", "bearish", "neutral"] = (
        "bearish"
        if iv_rank >= config.iv_rank_dir_bearish
        else "bullish" if iv_rank <= config.iv_rank_dir_bullish else "neutral"
    )

    signals = [
        {
            "name": _pt.name_atm_iv(lit),
            "value": round(atm_iv, 4),
            "direction": iv_dir,
            "explanation": _pt.expl_atm_iv_main(lit),
        },
        {
            "name": _pt.name_iv_rank(lit),
            "value": round(iv_rank, 4),
            "direction": rank_dir,
            "explanation": _pt.expl_iv_rank_main(lit),
        },
    ]
    return signals, {"atm_iv": round(atm_iv, 4), "iv_rank": iv_rank}
