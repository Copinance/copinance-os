"""Skew, butterfly, and simple term-structure signals."""

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
    numeric_greek,
)
from copinance_os.data.literacy import options_positioning as _pt
from copinance_os.domain.literacy import FinancialLiteracy
from copinance_os.domain.models.market import OptionContract
from copinance_os.domain.models.methodology import MethodologySpec


@dataclass(frozen=True, slots=True)
class SurfaceConfig:
    skew_steep_put: float = 3.0
    skew_call_skewed: float = -1.5
    term_contango: float = 0.75
    term_backwardation: float = -0.75
    skew_dir_bearish: float = 2.0
    skew_dir_bullish: float = -1.0


DEFAULT_SURFACE_CONFIG = SurfaceConfig()


def surface_methodology(config: SurfaceConfig) -> MethodologySpec:
    return MethodologySpec(
        id="options.positioning.surface",
        version="v1",
        model_family="delta_slice_skew_and_term_slope",
        assumptions=("25-delta IVs chosen by nearest delta match on the near slice.",),
        limitations=("Two-point term structure is coarse vs a full surface.",),
        references=(),
        parameters={
            "skew_steep_put": str(config.skew_steep_put),
            "term_contango": str(config.term_contango),
        },
    )


def compute_surface_signals(
    calls: list[OptionContract],
    puts: list[OptionContract],
    nearest_exp: str | None,
    second_exp: str | None,
    underlying: float,
    near_atm_iv: float,
    lit: FinancialLiteracy,
    config: SurfaceConfig = DEFAULT_SURFACE_CONFIG,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    skew_val = 0.0
    skew_expl = _pt.expl_skew_insufficient(lit)
    if nearest_exp and underlying > 0:
        c_near = contracts_for_expiration(calls, nearest_exp)
        p_near = contracts_for_expiration(puts, nearest_exp)
        c_candidates = [
            c
            for c in c_near
            if (contract_iv_pct(c) or 0.0) > 0
            and ((contract_oi(c) or 0) + (contract_vol(c) or 0)) > 0
        ]
        p_candidates = [
            p
            for p in p_near
            if (contract_iv_pct(p) or 0.0) > 0
            and ((contract_oi(p) or 0) + (contract_vol(p) or 0)) > 0
        ]
        if c_candidates:
            call_25 = min(
                c_candidates, key=lambda c: abs((numeric_greek(c, "delta") or 0.0) - 0.25)
            )
            call_iv = contract_iv_pct(call_25) or 0.0
        else:
            call_25 = None
            call_iv = 0.0
        if p_candidates:
            put_25 = min(p_candidates, key=lambda p: abs((numeric_greek(p, "delta") or 0.0) + 0.25))
            put_iv = contract_iv_pct(put_25) or 0.0
        else:
            put_25 = None
            put_iv = 0.0
        if call_25 is not None and put_25 is not None:
            skew_val = round(put_iv - call_iv, 4)
            skew_expl = _pt.expl_skew_ok(lit)

        skew_10_val = None
        butterfly_25 = None
        skew_regime: Literal["steep_put", "normal", "call_skewed"] | None = None
        if c_candidates:
            call_10 = min(
                c_candidates, key=lambda c: abs((numeric_greek(c, "delta") or 0.0) - 0.10)
            )
            call_10_iv = contract_iv_pct(call_10) or 0.0
        else:
            call_10 = None
            call_10_iv = 0.0
        if p_candidates:
            put_10 = min(p_candidates, key=lambda p: abs((numeric_greek(p, "delta") or 0.0) + 0.10))
            put_10_iv = contract_iv_pct(put_10) or 0.0
        else:
            put_10 = None
            put_10_iv = 0.0
        if call_10 is not None and put_10 is not None:
            skew_10_val = round(put_10_iv - call_10_iv, 4)
        if call_25 is not None and put_25 is not None:
            butterfly_25 = round((put_iv + call_iv) / 2.0 - near_atm_iv, 4)
        if skew_val > config.skew_steep_put:
            skew_regime = "steep_put"
        elif skew_val < config.skew_call_skewed:
            skew_regime = "call_skewed"
        else:
            skew_regime = "normal"
    else:
        skew_10_val = None
        butterfly_25 = None
        skew_regime = None

    far_atm_iv = 0.0
    slope: Literal["contango", "backwardation", "flat"] = "flat"
    slope_expl = _pt.expl_term_need_two(lit)
    if second_exp and underlying > 0:
        c2 = contracts_for_expiration(calls, second_exp)
        p2 = contracts_for_expiration(puts, second_exp)
        strikes2 = sorted(
            {
                contract_strike(x)
                for x in (*c2, *p2)
                if ((contract_oi(x) or 0) + (contract_vol(x) or 0)) > 0
                and (contract_iv_pct(x) or 0.0) > 0
            }
        )
        atm2 = atm_strike(strikes2, underlying)
        if atm2 is not None:
            ivs2: list[float] = []
            for c in c2:
                iv_pct = contract_iv_pct(c)
                if abs(contract_strike(c) - atm2) < 1e-6 and (iv_pct or 0.0) > 0:
                    ivs2.append(iv_pct or 0.0)
            for p in p2:
                iv_pct = contract_iv_pct(p)
                if abs(contract_strike(p) - atm2) < 1e-6 and (iv_pct or 0.0) > 0:
                    ivs2.append(iv_pct or 0.0)
            if ivs2:
                far_atm_iv = sum(ivs2) / len(ivs2)
                diff = far_atm_iv - near_atm_iv
                if diff > config.term_contango:
                    slope = "contango"
                elif diff < config.term_backwardation:
                    slope = "backwardation"
                else:
                    slope = "flat"
                slope_expl = _pt.expl_term_move(lit, near_atm_iv, far_atm_iv, slope)

    skew_dir: Literal["bullish", "bearish", "neutral"] = (
        "bearish"
        if skew_val > config.skew_dir_bearish
        else "bullish" if skew_val < config.skew_dir_bullish else "neutral"
    )
    term_dir: Literal["bullish", "bearish", "neutral"] = "neutral"

    signals = [
        {
            "name": _pt.name_skew_25d(lit),
            "value": skew_val,
            "direction": skew_dir,
            "explanation": skew_expl,
        },
        {
            "name": _pt.name_term_structure(lit),
            "value": round(far_atm_iv - near_atm_iv, 4) if second_exp else 0.0,
            "direction": term_dir,
            "explanation": slope_expl,
        },
    ]
    metrics = {
        "skew_25_delta": skew_val,
        "term_structure_slope": slope,
        "near_term_atm_iv": round(near_atm_iv, 4),
        "far_term_atm_iv": round(far_atm_iv, 4),
        "skew_10_delta": skew_10_val,
        "butterfly_25_delta": butterfly_25,
        "skew_regime": skew_regime,
    }
    return signals, metrics
