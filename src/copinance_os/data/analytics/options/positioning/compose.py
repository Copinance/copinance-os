"""Assemble the options-positioning payload dict (excluding envelope methodology)."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from copinance_os.data.analytics.options.positioning.bias import (
    apply_window_to_bias_score,
    bias_probabilities,
    compute_bias_score,
    compute_signal_agreement,
)
from copinance_os.data.analytics.options.positioning.charm import compute_charm_exposure
from copinance_os.data.analytics.options.positioning.config import PositioningMethodology
from copinance_os.data.analytics.options.positioning.contracts import (
    contract_iv_pct,
    contract_oi,
    contract_strike,
    contract_vol,
    nearest_expirations,
    numeric_greek,
    sorted_expirations,
)
from copinance_os.data.analytics.options.positioning.delta import compute_delta_exposure
from copinance_os.data.analytics.options.positioning.dollar import compute_dollar_metrics
from copinance_os.data.analytics.options.positioning.flow import compute_flow_signals
from copinance_os.data.analytics.options.positioning.gex import (
    compute_gamma_regime,
    compute_gex_profile,
)
from copinance_os.data.analytics.options.positioning.implied_move import compute_implied_move
from copinance_os.data.analytics.options.positioning.math import safe_float
from copinance_os.data.analytics.options.positioning.mispricing import compute_mispricing
from copinance_os.data.analytics.options.positioning.moneyness import (
    compute_moneyness_buckets,
    moneyness_flow_direction,
)
from copinance_os.data.analytics.options.positioning.oi_clusters import (
    compute_max_pain,
    oi_clusters_by_strike,
    oi_clusters_enhanced,
)
from copinance_os.data.analytics.options.positioning.pin_risk import compute_pin_risk
from copinance_os.data.analytics.options.positioning.quality import compute_data_quality
from copinance_os.data.analytics.options.positioning.scenarios import build_scenarios
from copinance_os.data.analytics.options.positioning.surface import compute_surface_signals
from copinance_os.data.analytics.options.positioning.vanna import compute_vanna_exposure
from copinance_os.data.analytics.options.positioning.volatility import compute_volatility_signals
from copinance_os.data.literacy import options_positioning as _pt
from copinance_os.domain.literacy import FinancialLiteracy
from copinance_os.domain.models.market import OptionContract, OptionsChain


def compose_options_positioning_payload(
    *,
    chain: OptionsChain,
    calls: list[OptionContract],
    puts: list[OptionContract],
    quote: dict[str, Any],
    symbol: str,
    window: Literal["near", "mid"],
    lit: FinancialLiteracy,
    ref_date: date,
    methodology: PositioningMethodology,
) -> dict[str, Any]:
    up = chain.underlying_price
    underlying = safe_float(up, safe_float(quote.get("current_price")))

    sorted_exp = sorted_expirations(chain, calls, puts)
    near_exps = nearest_expirations(sorted_exp, 2)
    nearest_exp = near_exps[0] if near_exps else None
    second_exp = near_exps[1] if len(near_exps) > 1 else None

    mc = methodology
    data_quality = compute_data_quality(calls, puts, underlying, mc.quality)
    dollar_metrics_dict = compute_dollar_metrics(calls, puts, mc.dollar)
    delta_exposure_dict = compute_delta_exposure(calls, puts, underlying, mc.delta)
    gex_bundle = compute_gex_profile(calls, puts, nearest_exp, underlying, mc.gex)
    oi_enhanced_bundle = oi_clusters_enhanced(calls, puts, nearest_exp, top_n=mc.oi_clusters.top_n)
    vanna_bundle = compute_vanna_exposure(calls, puts, nearest_exp, underlying, mc.vanna)
    charm_bundle = compute_charm_exposure(calls, puts, mc.charm)
    mispricing_bundle = compute_mispricing(calls, puts, mc.mispricing)
    moneyness_bundle = compute_moneyness_buckets(calls, puts, mc.moneyness)
    pin_bundle = compute_pin_risk(calls, puts, nearest_exp, underlying, ref_date, mc.pin_risk)

    call_oi = sum(contract_oi(c) for c in calls)
    put_oi = sum(contract_oi(p) for p in puts)
    call_vol = sum(contract_vol(c) for c in calls)
    put_vol = sum(contract_vol(p) for p in puts)

    total_oi = max(1, call_oi + put_oi)
    total_vol = max(1, call_vol + put_vol)

    call_oi_ratio = call_oi / total_oi
    put_call_oi_ratio = put_oi / max(1, call_oi)
    call_flow_ratio = call_vol / total_vol

    weighted_gamma_calls = sum(numeric_greek(c, "gamma") * float(contract_oi(c)) for c in calls)
    weighted_gamma_puts = sum(numeric_greek(p, "gamma") * float(contract_oi(p)) for p in puts)
    gamma_tilt = (weighted_gamma_calls - weighted_gamma_puts) / max(
        1.0, abs(weighted_gamma_calls) + abs(weighted_gamma_puts)
    )

    dollar_tot_vol = (
        dollar_metrics_dict["dollar_call_volume"] + dollar_metrics_dict["dollar_put_volume"]
    )
    call_flow_share_score = (
        dollar_metrics_dict["dollar_call_flow_share"] if dollar_tot_vol > 0.0 else call_flow_ratio
    )

    score = compute_bias_score(
        call_oi_ratio,
        call_flow_share_score,
        gamma_tilt,
        put_call_oi_ratio,
        dollar_metrics_dict["dollar_put_call_oi_ratio"],
        delta_exposure_dict["net_delta"],
        dollar_metrics_dict["dollar_call_oi"],
        mc.bias,
    )
    score = apply_window_to_bias_score(score, window, mc.bias)

    bullish_probability, bearish_probability, neutral_probability = bias_probabilities(score)

    if bullish_probability >= bearish_probability and bullish_probability >= neutral_probability:
        bias: Literal["bullish", "bearish", "neutral"] = "bullish"
        confidence = bullish_probability
    elif bearish_probability >= bullish_probability and bearish_probability >= neutral_probability:
        bias = "bearish"
        confidence = bearish_probability
    else:
        bias = "neutral"
        confidence = neutral_probability

    confidence *= 0.5 + 0.5 * data_quality

    strikes = sorted({round(contract_strike(c), 2) for c in (*calls, *puts) if contract_oi(c) > 0})
    around_spot = sorted(strikes, key=lambda s: abs(s - underlying))[:3] if strikes else []

    dcf = dollar_metrics_dict["dollar_call_flow_share"]
    dpc = dollar_metrics_dict["dollar_put_call_oi_ratio"]

    signals = [
        {
            "name": _pt.name_call_oi_share(lit),
            "value": round(call_oi_ratio, 3),
            "direction": (
                "bullish"
                if call_oi_ratio >= 0.52
                else "bearish" if call_oi_ratio <= 0.45 else "neutral"
            ),
            "explanation": _pt.expl_call_oi_share(lit),
        },
        {
            "name": _pt.name_put_call_oi(lit),
            "value": round(put_call_oi_ratio, 3),
            "direction": (
                "bearish"
                if put_call_oi_ratio >= 1.1
                else "bullish" if put_call_oi_ratio <= 0.9 else "neutral"
            ),
            "explanation": _pt.expl_put_call_oi(lit),
        },
        {
            "name": _pt.name_flow_calls_share(lit),
            "value": round(call_flow_ratio, 3),
            "direction": (
                "bullish"
                if call_flow_ratio >= 0.53
                else "bearish" if call_flow_ratio <= 0.47 else "neutral"
            ),
            "explanation": _pt.expl_flow_calls_share(lit),
        },
        {
            "name": _pt.name_gamma_tilt(lit),
            "value": round(gamma_tilt, 3),
            "direction": (
                "bullish" if gamma_tilt > 0.05 else "bearish" if gamma_tilt < -0.05 else "neutral"
            ),
            "explanation": _pt.expl_gamma_tilt(lit),
        },
        {
            "name": _pt.name_dollar_call_flow_share(lit),
            "value": round(dcf, 4),
            "direction": ("bullish" if dcf >= 0.53 else "bearish" if dcf <= 0.47 else "neutral"),
            "explanation": _pt.expl_dollar_call_flow_share(lit),
        },
        {
            "name": _pt.name_dollar_put_call_oi(lit),
            "value": round(dpc, 4),
            "direction": ("bearish" if dpc >= 1.1 else "bullish" if dpc <= 0.9 else "neutral"),
            "explanation": _pt.expl_dollar_put_call_oi(lit),
        },
    ]

    all_iv_samples = [
        contract_iv_pct(c)
        for c in (*calls, *puts)
        if contract_iv_pct(c) > 0 and (contract_oi(c) + contract_vol(c)) > 0
    ]

    vol_sigs, vol_partial = compute_volatility_signals(
        calls, puts, nearest_exp, underlying, all_iv_samples, lit, mc.volatility
    )
    near_atm = float(vol_partial.get("atm_iv") or 0.0)
    surface_sigs, surface_partial = compute_surface_signals(
        calls, puts, nearest_exp, second_exp, underlying, near_atm, lit, mc.surface
    )

    iv_rank_val = float(vol_partial.get("iv_rank") or 0.5)
    volatility_category: list[dict[str, Any]]
    if len(vol_sigs) >= 2:
        atm_row = vol_sigs[0]
        volatility_category = [
            {
                "name": _pt.name_vol_combo_atm_iv_rank(lit),
                "value": float(atm_row.get("value") or 0.0),
                "direction": atm_row.get("direction", "neutral"),
                "explanation": _pt.expl_vol_combo(
                    lit, float(atm_row.get("value") or 0.0), iv_rank_val
                ),
            }
        ]
    else:
        volatility_category = list(vol_sigs)
    volatility_category.extend(surface_sigs)

    iv_metrics = {
        "atm_iv": float(vol_partial.get("atm_iv") or 0.0),
        "skew_25_delta": float(surface_partial.get("skew_25_delta") or 0.0),
        "term_structure_slope": surface_partial["term_structure_slope"],
        "near_term_atm_iv": float(surface_partial.get("near_term_atm_iv") or 0.0),
        "far_term_atm_iv": float(surface_partial.get("far_term_atm_iv") or 0.0),
        "skew_10_delta": surface_partial.get("skew_10_delta"),
        "butterfly_25_delta": surface_partial.get("butterfly_25_delta"),
        "skew_regime": surface_partial.get("skew_regime"),
    }

    flow_sigs = compute_flow_signals(calls, puts, lit, mc.flow)
    if mispricing_bundle is not None:
        mp_row = mispricing_bundle["mispricing"]
        mp_dir: Literal["bullish", "bearish", "neutral"] = (
            "bullish"
            if mp_row["sentiment"] == "call_demand"
            else "bearish" if mp_row["sentiment"] == "put_demand" else "neutral"
        )
        flow_sigs.append(
            {
                "name": _pt.name_bsm_mispricing(lit),
                "value": round(mp_row["call_avg_mispricing_pct"], 4),
                "direction": mp_dir,
                "explanation": _pt.expl_bsm_mispricing(
                    lit,
                    float(mp_row["call_avg_mispricing_pct"]),
                    float(mp_row["put_avg_mispricing_pct"]),
                    str(mp_row["sentiment"]),
                ),
            }
        )
    ms_row = moneyness_bundle["moneyness_summary"]
    mom_dir = moneyness_flow_direction(
        ms_row.get("dominant_call_bucket"), ms_row.get("dominant_put_bucket")
    )
    _mom_rank = {"deep_itm": 1.0, "itm": 2.0, "atm": 3.0, "otm": 4.0, "deep_otm": 5.0}
    _dc = ms_row.get("dominant_call_bucket")
    _dp = ms_row.get("dominant_put_bucket")
    mom_val = _mom_rank.get(_dc or "atm", 3.0) + 0.1 * _mom_rank.get(_dp or "atm", 3.0)
    flow_sigs.append(
        {
            "name": _pt.name_dominant_flow_moneyness(lit),
            "value": round(mom_val, 4),
            "direction": mom_dir,
            "explanation": _pt.expl_dominant_flow_moneyness(
                lit,
                ms_row.get("dominant_call_bucket"),
                ms_row.get("dominant_put_bucket"),
            ),
        }
    )

    gamma_sigs, _net_g, regime, regime_explanation = compute_gamma_regime(
        calls, puts, underlying, lit, mc.gex
    )

    gf_strike = gex_bundle["gamma_flip_strike"]
    gamma_flip_dir: Literal["bullish", "bearish", "neutral"] = "neutral"
    if gf_strike is not None and underlying > 0:
        gamma_flip_dir = "bullish" if underlying > float(gf_strike) else "bearish"
    gamma_sigs = [
        *gamma_sigs,
        {
            "name": _pt.name_gamma_flip_strike(lit),
            "value": float(gf_strike) if gf_strike is not None else 0.0,
            "direction": gamma_flip_dir,
            "explanation": _pt.expl_gamma_flip_strike(lit, gf_strike, underlying),
        },
        {
            "name": _pt.name_net_delta_exposure(lit),
            "value": round(delta_exposure_dict["net_delta"], 4),
            "direction": (
                "bullish"
                if delta_exposure_dict["net_delta"] > 0
                else "bearish" if delta_exposure_dict["net_delta"] < 0 else "neutral"
            ),
            "explanation": _pt.expl_net_delta_exposure(lit),
        },
    ]

    vex = vanna_bundle.get("vanna_exposure")
    if vex is not None:
        vanna_dir: Literal["bullish", "bearish", "neutral"] = (
            "bearish"
            if vex["regime"] == "short_vanna"
            else "bullish" if vex["regime"] == "long_vanna" else "neutral"
        )
        gamma_sigs.append(
            {
                "name": _pt.name_vanna_exposure(lit),
                "value": round(float(vex["net_vanna"]), 4),
                "direction": vanna_dir,
                "explanation": _pt.expl_vanna_exposure(lit, str(vex["regime"])),
            }
        )
    ch_row = charm_bundle.get("charm_exposure")
    if ch_row is not None:
        charm_dir: Literal["bullish", "bearish", "neutral"] = (
            "bearish"
            if ch_row["overnight_delta_drift"] == "selling_pressure"
            else "bullish" if ch_row["overnight_delta_drift"] == "buying_pressure" else "neutral"
        )
        gamma_sigs.append(
            {
                "name": _pt.name_charm_exposure(lit),
                "value": round(float(ch_row["net_charm"]), 4),
                "direction": charm_dir,
                "explanation": _pt.expl_charm_exposure(lit, str(ch_row["overnight_delta_drift"])),
            }
        )

    max_pain_strike = compute_max_pain(calls, puts, nearest_exp)
    implied_move_pct, _implied_move_abs, implied_move_detail = compute_implied_move(
        calls, puts, nearest_exp, underlying, ref_date, mc.implied_move
    )
    oi_clusters = oi_clusters_by_strike(calls, puts, nearest_exp, top_n=mc.oi_clusters.top_n)

    max_pain_val = float(max_pain_strike) if max_pain_strike is not None else 0.0

    structure_sigs = [
        {
            "name": _pt.name_max_pain(lit),
            "value": round(max_pain_val, 4) if max_pain_strike else 0.0,
            "direction": "neutral",
            "explanation": _pt.expl_max_pain(lit),
        },
        {
            "name": _pt.name_strike_magnets(lit),
            "value": float(len(oi_clusters)),
            "direction": "neutral",
            "explanation": _pt.expl_strike_magnets(lit),
        },
        {
            "name": _pt.name_implied_move(lit),
            "value": implied_move_pct,
            "direction": "neutral",
            "explanation": _pt.expl_implied_move(lit, implied_move_detail),
        },
    ]

    if pin_bundle is not None:
        pin_lvl = str(pin_bundle["pin_risk_level"])
        pin_val = 0.33 if pin_lvl == "low" else 0.66 if pin_lvl == "moderate" else 1.0
        structure_sigs.append(
            {
                "name": _pt.name_pin_risk(lit),
                "value": pin_val,
                "direction": "neutral",
                "explanation": _pt.expl_pin_risk(lit, pin_bundle),
            }
        )

    signal_categories = {
        "positioning": signals,
        "volatility": volatility_category,
        "flow": flow_sigs,
        "gamma": gamma_sigs,
        "structure": structure_sigs,
    }
    signal_agreement = compute_signal_agreement(
        signal_categories["positioning"],
        signal_categories["flow"],
        signal_categories["gamma"],
    )

    cw = oi_enhanced_bundle["call_wall"]
    pw = oi_enhanced_bundle["put_wall"]

    return {
        "symbol": symbol,
        "window": window,
        "confidence": round(confidence, 4),
        "market_bias": bias,
        "bullish_probability": round(bullish_probability, 4),
        "bearish_probability": round(bearish_probability, 4),
        "neutral_probability": round(neutral_probability, 4),
        "key_levels": around_spot,
        "analyst_summary": _pt.analyst_summary(symbol, bias, confidence, window, lit),
        "signal_categories": signal_categories,
        "regime": regime,
        "regime_explanation": regime_explanation,
        "iv_metrics": iv_metrics,
        "max_pain": max_pain_val if max_pain_strike is not None else None,
        "implied_move_detail": implied_move_detail,
        "oi_clusters": oi_clusters,
        "data_quality": round(data_quality, 4),
        "dollar_metrics": {
            "dollar_call_oi": round(dollar_metrics_dict["dollar_call_oi"], 4),
            "dollar_put_oi": round(dollar_metrics_dict["dollar_put_oi"], 4),
            "dollar_put_call_oi_ratio": round(dollar_metrics_dict["dollar_put_call_oi_ratio"], 4),
            "dollar_call_volume": round(dollar_metrics_dict["dollar_call_volume"], 4),
            "dollar_put_volume": round(dollar_metrics_dict["dollar_put_volume"], 4),
            "dollar_call_flow_share": round(dollar_metrics_dict["dollar_call_flow_share"], 4),
        },
        "gamma_flip_strike": gf_strike,
        "gex_profile": gex_bundle["gex_profile"],
        "top_positive_gex": gex_bundle["top_positive_gex"],
        "top_negative_gex": gex_bundle["top_negative_gex"],
        "delta_exposure": {
            "net_delta": round(delta_exposure_dict["net_delta"], 4),
            "dollar_delta": round(delta_exposure_dict["dollar_delta"], 4),
            "call_delta_exposure": round(delta_exposure_dict["call_delta_exposure"], 4),
            "put_delta_exposure": round(delta_exposure_dict["put_delta_exposure"], 4),
        },
        "oi_clusters_enhanced": oi_enhanced_bundle["clusters"],
        "call_wall": float(cw) if cw is not None else None,
        "put_wall": float(pw) if pw is not None else None,
        "signal_agreement": signal_agreement,
        "vanna_exposure": vanna_bundle.get("vanna_exposure"),
        "vanna_profile": vanna_bundle.get("vanna_profile", []),
        "charm_exposure": charm_bundle.get("charm_exposure"),
        "mispricing": mispricing_bundle.get("mispricing") if mispricing_bundle else None,
        "moneyness_summary": moneyness_bundle.get("moneyness_summary"),
        "pin_risk": pin_bundle,
        "scenarios": build_scenarios(
            symbol, lit, bullish_probability, bearish_probability, neutral_probability
        ),
    }
