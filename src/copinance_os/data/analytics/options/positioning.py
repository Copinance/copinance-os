"""Core computation for options surface positioning (ported from Copinance backend)."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import date, datetime
from typing import Any, Literal

from copinance_os.data.analytics.options.contract_numeric import contract_numeric
from copinance_os.domain.models.market import OptionContract, OptionsChain
from copinance_os.domain.models.options_positioning import OptionsPositioningResult
from copinance_os.domain.ports.data_providers import MarketDataProvider


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize(value: float, min_v: float, max_v: float) -> float:
    if max_v <= min_v:
        return 0.5
    clamped = max(min_v, min(value, max_v))
    return (clamped - min_v) / (max_v - min_v)


def _sigmoid(x: float) -> float:
    if x > 30:
        return 1.0
    if x < -30:
        return 0.0
    return float(1.0 / (1.0 + math.exp(-x)))


def _contract_strike(c: OptionContract) -> float:
    return _safe_float(c.strike)


def _contract_expiration_iso(c: OptionContract) -> str:
    return c.expiration_date.isoformat()


def _contract_oi(c: OptionContract) -> int:
    v = c.open_interest
    if v is None:
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _contract_vol(c: OptionContract) -> int:
    v = c.volume
    if v is None:
        return 0
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _contract_iv_pct(c: OptionContract) -> float:
    raw = c.implied_volatility
    if raw is None:
        return 0.0
    iv = _safe_float(raw)
    if iv <= 0:
        return 0.0
    if iv < 2.0:
        iv *= 100.0
    return iv


def _contract_bid_ask(c: OptionContract) -> tuple[float, float]:
    bid = _safe_float(c.bid)
    ask = _safe_float(c.ask)
    return bid, ask


def _sorted_expirations(
    chain: OptionsChain, calls: list[OptionContract], puts: list[OptionContract]
) -> list[str]:
    out: set[str] = set()
    for e in chain.available_expirations or []:
        if isinstance(e, date):
            out.add(e.isoformat())
        elif hasattr(e, "isoformat"):
            out.add(str(e.date() if isinstance(e, datetime) else e))
        else:
            out.add(str(e).strip())
    for c in (*calls, *puts):
        out.add(_contract_expiration_iso(c))
    return sorted(out)


def _expiration_sort_key(s: str) -> tuple[int, str]:
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(s, fmt).date()
            return (0, dt.isoformat())
        except ValueError:
            continue
    return (1, s)


def _nearest_expirations(sorted_exp: list[str], n: int = 2) -> list[str]:
    if not sorted_exp:
        return []
    ordered = sorted(sorted_exp, key=_expiration_sort_key)
    return ordered[:n]


def _atm_strike(strikes: list[float], underlying: float) -> float | None:
    if not strikes or underlying <= 0:
        return None
    return min(strikes, key=lambda s: abs(s - underlying))


def _contracts_for_expiration(contracts: list[OptionContract], exp: str) -> list[OptionContract]:
    return [c for c in contracts if _contract_expiration_iso(c) == exp]


def _percentile_rank(value: float, samples: list[float]) -> float:
    if not samples:
        return 0.5
    arr = sorted(samples)
    below = sum(1 for x in arr if x < value)
    return below / max(1, len(arr))


def _compute_volatility_signals(
    calls: list[OptionContract],
    puts: list[OptionContract],
    nearest_exp: str | None,
    underlying: float,
    all_iv_samples: list[float],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not nearest_exp or underlying <= 0:
        return (
            [
                {
                    "name": "ATM Implied Volatility",
                    "value": 0.0,
                    "direction": "neutral",
                    "explanation": "Insufficient chain or spot data to estimate ATM implied volatility.",
                },
                {
                    "name": "Intra-Chain IV Rank",
                    "value": 0.5,
                    "direction": "neutral",
                    "explanation": "IV rank unavailable without a usable volatility sample across the chain.",
                },
            ],
            {"atm_iv": 0.0, "iv_rank": 0.5},
        )

    c_near = _contracts_for_expiration(calls, nearest_exp)
    p_near = _contracts_for_expiration(puts, nearest_exp)
    strikes = sorted(
        {
            _contract_strike(x)
            for x in (*c_near, *p_near)
            if _contract_oi(x) + _contract_vol(x) > 0 and _contract_iv_pct(x) > 0
        }
    )
    atm = _atm_strike(strikes, underlying)
    if atm is None:
        return (
            [
                {
                    "name": "ATM Implied Volatility",
                    "value": 0.0,
                    "direction": "neutral",
                    "explanation": "No quoted implied volatility near the money for the nearest expiration.",
                },
                {
                    "name": "Intra-Chain IV Rank",
                    "value": round(_percentile_rank(0.0, all_iv_samples), 4),
                    "direction": "neutral",
                    "explanation": "How current ATM IV ranks versus all IV prints in this chain snapshot.",
                },
            ],
            {"atm_iv": 0.0, "iv_rank": _percentile_rank(0.0, all_iv_samples)},
        )

    atm_ivs: list[float] = []
    for c in c_near:
        if abs(_contract_strike(c) - atm) < 1e-6 and _contract_iv_pct(c) > 0:
            atm_ivs.append(_contract_iv_pct(c))
    for p in p_near:
        if abs(_contract_strike(p) - atm) < 1e-6 and _contract_iv_pct(p) > 0:
            atm_ivs.append(_contract_iv_pct(p))
    atm_iv = sum(atm_ivs) / len(atm_ivs) if atm_ivs else 0.0

    iv_rank = _percentile_rank(atm_iv, all_iv_samples) if all_iv_samples else 0.5
    iv_dir: Literal["bullish", "bearish", "neutral"] = (
        "bearish" if iv_rank >= 0.72 else "bullish" if iv_rank <= 0.35 else "neutral"
    )
    rank_dir: Literal["bullish", "bearish", "neutral"] = (
        "bearish" if iv_rank >= 0.65 else "bullish" if iv_rank <= 0.4 else "neutral"
    )

    signals = [
        {
            "name": "ATM Implied Volatility",
            "value": round(atm_iv, 4),
            "direction": iv_dir,
            "explanation": (
                "At-the-money implied volatility for the nearest listed expiration — "
                "the market’s baseline fear / demand for premium at spot."
            ),
        },
        {
            "name": "Intra-Chain IV Rank",
            "value": round(iv_rank, 4),
            "direction": rank_dir,
            "explanation": (
                "Percentile of ATM IV versus all implied volatilities observed in this chain snapshot "
                "(0 = lowest, 1 = highest)."
            ),
        },
    ]
    return signals, {"atm_iv": round(atm_iv, 4), "iv_rank": iv_rank}


def _compute_surface_signals(
    calls: list[OptionContract],
    puts: list[OptionContract],
    nearest_exp: str | None,
    second_exp: str | None,
    underlying: float,
    near_atm_iv: float,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    skew_val = 0.0
    skew_expl = "Not enough delta quotes to estimate 25-delta skew for the nearest expiration."
    if nearest_exp and underlying > 0:
        c_near = _contracts_for_expiration(calls, nearest_exp)
        p_near = _contracts_for_expiration(puts, nearest_exp)
        c_candidates = [
            c
            for c in c_near
            if _contract_iv_pct(c) > 0 and (_contract_oi(c) + _contract_vol(c)) > 0
        ]
        p_candidates = [
            p
            for p in p_near
            if _contract_iv_pct(p) > 0 and (_contract_oi(p) + _contract_vol(p)) > 0
        ]
        if c_candidates:
            call_25 = min(c_candidates, key=lambda c: abs(contract_numeric(c, "delta") - 0.25))
            call_iv = _contract_iv_pct(call_25)
        else:
            call_25 = None
            call_iv = 0.0
        if p_candidates:
            put_25 = min(p_candidates, key=lambda p: abs(contract_numeric(p, "delta") + 0.25))
            put_iv = _contract_iv_pct(put_25)
        else:
            put_25 = None
            put_iv = 0.0
        if call_25 is not None and put_25 is not None:
            skew_val = round(put_iv - call_iv, 4)
            skew_expl = (
                "IV of the ~25-delta put minus the ~25-delta call (nearest expiry). "
                "Positive skew often reflects downside protection demand."
            )

    far_atm_iv = 0.0
    slope: Literal["contango", "backwardation", "flat"] = "flat"
    slope_expl = "Need two expirations with ATM IV to infer term structure."
    if second_exp and underlying > 0:
        c2 = _contracts_for_expiration(calls, second_exp)
        p2 = _contracts_for_expiration(puts, second_exp)
        strikes2 = sorted(
            {
                _contract_strike(x)
                for x in (*c2, *p2)
                if _contract_oi(x) + _contract_vol(x) > 0 and _contract_iv_pct(x) > 0
            }
        )
        atm2 = _atm_strike(strikes2, underlying)
        if atm2 is not None:
            ivs2: list[float] = []
            for c in c2:
                if abs(_contract_strike(c) - atm2) < 1e-6 and _contract_iv_pct(c) > 0:
                    ivs2.append(_contract_iv_pct(c))
            for p in p2:
                if abs(_contract_strike(p) - atm2) < 1e-6 and _contract_iv_pct(p) > 0:
                    ivs2.append(_contract_iv_pct(p))
            if ivs2:
                far_atm_iv = sum(ivs2) / len(ivs2)
                diff = far_atm_iv - near_atm_iv
                if diff > 0.75:
                    slope = "contango"
                elif diff < -0.75:
                    slope = "backwardation"
                else:
                    slope = "flat"
                slope_expl = (
                    f"ATM IV moves from {near_atm_iv:.1f}% (near) to {far_atm_iv:.1f}% (next slice) — "
                    f"{slope.replace('_', ' ')}."
                )

    skew_dir: Literal["bullish", "bearish", "neutral"] = (
        "bearish" if skew_val > 2.0 else "bullish" if skew_val < -1.0 else "neutral"
    )
    term_dir: Literal["bullish", "bearish", "neutral"] = "neutral"

    signals = [
        {
            "name": "25-Delta Skew",
            "value": skew_val,
            "direction": skew_dir,
            "explanation": skew_expl,
        },
        {
            "name": "Term Structure",
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
    }
    return signals, metrics


def _compute_flow_signals(
    calls: list[OptionContract], puts: list[OptionContract]
) -> list[dict[str, Any]]:
    flagged = 0
    vol_threshold = 500
    for c in (*calls, *puts):
        oi = max(1, _contract_oi(c))
        vol = _contract_vol(c)
        ratio = vol / oi
        if ratio > 2.0 and vol > vol_threshold:
            flagged += 1

    chain_vol = sum(_contract_vol(c) for c in calls) + sum(_contract_vol(p) for p in puts)
    chain_oi = sum(_contract_oi(c) for c in calls) + sum(_contract_oi(p) for p in puts)
    agg_ratio = chain_vol / max(1, chain_oi)

    unusual_score = min(100.0, float(flagged) * 12.0 + max(0.0, agg_ratio - 1.5) * 10.0)
    unusual_score = round(unusual_score, 4)

    unusual_dir: Literal["bullish", "bearish", "neutral"] = (
        "bullish" if unusual_score >= 40 else "neutral"
    )
    flow_dir: Literal["bullish", "bearish", "neutral"] = (
        "bullish" if agg_ratio >= 0.35 else "bearish" if agg_ratio <= 0.12 else "neutral"
    )

    return [
        {
            "name": "Unusual Activity Score",
            "value": unusual_score,
            "direction": unusual_dir,
            "explanation": (
                f"Counts strikes where volume is elevated versus open interest (ratio > 2, "
                f"volume > {vol_threshold}), scaled into a 0–100-style intensity score."
            ),
        },
        {
            "name": "Aggregate Volume / OI",
            "value": round(agg_ratio, 4),
            "direction": flow_dir,
            "explanation": (
                "Total options volume divided by total open interest — higher values can "
                "indicate more tactical trading versus stuck inventory."
            ),
        },
    ]


def _compute_gamma_regime(
    calls: list[OptionContract], puts: list[OptionContract], underlying: float
) -> tuple[
    list[dict[str, Any]], float, Literal["positive_gamma", "negative_gamma", "neutral"], str
]:
    net = 0.0
    gross = 0.0
    mult = 100.0 * max(underlying, 1e-9)
    for c in calls:
        g = contract_numeric(c, "gamma")
        oi = _contract_oi(c)
        contrib = g * oi * mult
        net += contrib
        gross += abs(contrib)
    for p in puts:
        g = contract_numeric(p, "gamma")
        oi = _contract_oi(p)
        contrib = g * oi * mult
        net -= contrib
        gross += abs(contrib)

    if gross < 1e-6:
        regime: Literal["positive_gamma", "negative_gamma", "neutral"] = "neutral"
        expl = "Gamma exposure is negligible in this snapshot — regime is effectively neutral."
    else:
        rel = net / gross
        if rel > 0.06:
            regime = "positive_gamma"
            expl = (
                "Net gamma is positive — dealers are more likely to stabilize moves "
                "(fade extremes) if this positioning persists."
            )
        elif rel < -0.06:
            regime = "negative_gamma"
            expl = (
                "Net gamma is negative — convexity can amplify moves as hedgers chase delta "
                "in trending conditions."
            )
        else:
            regime = "neutral"
            expl = "Gamma is balanced — neither strong stabilization nor strong convexity amplification."

    net_rounded = round(net, 4)
    signals = [
        {
            "name": "Net Gamma Exposure",
            "value": net_rounded,
            "direction": "bullish" if net > 0 else "bearish" if net < 0 else "neutral",
            "explanation": (
                "Sum of gamma × OI × 100 × spot for calls minus puts — a coarse dealer-gamma proxy."
            ),
        },
        {
            "name": "Gamma Regime",
            "value": (
                1.0 if regime == "positive_gamma" else -1.0 if regime == "negative_gamma" else 0.0
            ),
            "direction": (
                "bullish"
                if regime == "positive_gamma"
                else "bearish" if regime == "negative_gamma" else "neutral"
            ),
            "explanation": expl,
        },
    ]
    return signals, net_rounded, regime, expl


def _compute_max_pain(
    calls: list[OptionContract], puts: list[OptionContract], nearest_exp: str | None
) -> float | None:
    if not nearest_exp:
        return None
    c_exp = _contracts_for_expiration(calls, nearest_exp)
    p_exp = _contracts_for_expiration(puts, nearest_exp)
    strikes_set = {_contract_strike(c) for c in c_exp} | {_contract_strike(p) for p in p_exp}
    strikes = sorted(s for s in strikes_set if s > 0)
    if not strikes:
        return None

    def intrinsic_at(spot: float) -> float:
        total = 0.0
        for c in c_exp:
            k = _contract_strike(c)
            oi = _contract_oi(c)
            total += max(0.0, spot - k) * oi * 100.0
        for p in p_exp:
            k = _contract_strike(p)
            oi = _contract_oi(p)
            total += max(0.0, k - spot) * oi * 100.0
        return total

    return min(strikes, key=lambda s: intrinsic_at(s))


def _oi_clusters_by_strike(
    calls: list[OptionContract], puts: list[OptionContract], nearest_exp: str | None, top_n: int = 8
) -> list[dict[str, float]]:
    if not nearest_exp:
        return []
    oi_by: dict[float, int] = defaultdict(int)
    for c in _contracts_for_expiration(calls, nearest_exp):
        oi_by[_contract_strike(c)] += _contract_oi(c)
    for p in _contracts_for_expiration(puts, nearest_exp):
        oi_by[_contract_strike(p)] += _contract_oi(p)
    ranked = sorted(oi_by.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    return [{"strike": float(k), "open_interest": float(v)} for k, v in ranked if v > 0]


def _compute_implied_move(
    calls: list[OptionContract],
    puts: list[OptionContract],
    nearest_exp: str | None,
    underlying: float,
) -> tuple[float, float]:
    if not nearest_exp or underlying <= 0:
        return 0.0, 0.0
    c_near = _contracts_for_expiration(calls, nearest_exp)
    p_near = _contracts_for_expiration(puts, nearest_exp)
    strikes = sorted(
        {_contract_strike(c) for c in c_near if _contract_oi(c) + _contract_vol(c) > 0}
        & {_contract_strike(p) for p in p_near if _contract_oi(p) + _contract_vol(p) > 0}
    )
    atm = _atm_strike(strikes, underlying)
    if atm is None:
        return 0.0, 0.0
    call_mid = 0.0
    put_mid = 0.0
    found_c = found_p = False
    for c in c_near:
        if abs(_contract_strike(c) - atm) < 1e-6:
            bid, ask = _contract_bid_ask(c)
            if bid > 0 or ask > 0:
                call_mid = (bid + ask) / 2.0 if ask >= bid else max(bid, ask)
                found_c = True
                break
    for p in p_near:
        if abs(_contract_strike(p) - atm) < 1e-6:
            bid, ask = _contract_bid_ask(p)
            if bid > 0 or ask > 0:
                put_mid = (bid + ask) / 2.0 if ask >= bid else max(bid, ask)
                found_p = True
                break
    if not (found_c and found_p):
        return 0.0, 0.0
    straddle = call_mid + put_mid
    pct = (straddle / underlying) * 100.0
    return round(pct, 4), round(straddle, 4)


def _build_analyst_summary(symbol: str, bias: str, confidence: float, window: str) -> str:
    tone = (
        "the aggregate options surface leans bullish — more call-heavy OI and flow"
        if bias == "bullish"
        else (
            "the aggregate options surface leans bearish — more defensive put weight "
            "or softer call demand"
            if bias == "bearish"
            else "the options surface is mixed — no strong one-sided aggregate skew yet"
        )
    )
    horizon = "next 1-2 weeks" if window == "near" else "next 1-2 months"
    return (
        f"For {symbol}, {tone}. That reflects overall market positioning in the chain, "
        f"not a specific actor; heavy clusters can sometimes line up with large books, "
        f"but we do not label institutions. "
        f"Model confidence is {confidence * 100:.0f}% for the {horizon} horizon."
    )


def build_options_positioning_dict(
    chain: OptionsChain,
    calls: list[OptionContract],
    puts: list[OptionContract],
    quote: dict[str, Any],
    symbol: str,
    window: Literal["near", "mid"],
) -> dict[str, Any]:
    """Build the full positioning payload dict (validated by ``OptionsPositioningResult``)."""
    up = chain.underlying_price
    underlying = _safe_float(up, _safe_float(quote.get("current_price")))

    call_oi = sum(_contract_oi(c) for c in calls)
    put_oi = sum(_contract_oi(p) for p in puts)
    call_vol = sum(_contract_vol(c) for c in calls)
    put_vol = sum(_contract_vol(p) for p in puts)

    total_oi = max(1, call_oi + put_oi)
    total_vol = max(1, call_vol + put_vol)

    call_oi_ratio = call_oi / total_oi
    put_call_oi_ratio = put_oi / max(1, call_oi)
    call_flow_ratio = call_vol / total_vol

    weighted_gamma_calls = sum(contract_numeric(c, "gamma") * float(_contract_oi(c)) for c in calls)
    weighted_gamma_puts = sum(contract_numeric(p, "gamma") * float(_contract_oi(p)) for p in puts)
    gamma_tilt = (weighted_gamma_calls - weighted_gamma_puts) / max(
        1.0, abs(weighted_gamma_calls) + abs(weighted_gamma_puts)
    )

    score = (
        (_normalize(call_oi_ratio, 0.35, 0.65) - 0.5) * 1.8
        + (_normalize(call_flow_ratio, 0.35, 0.65) - 0.5) * 1.6
        + (_normalize(gamma_tilt, -0.4, 0.4) - 0.5) * 1.4
        - (_normalize(put_call_oi_ratio, 0.7, 1.6) - 0.5) * 1.2
    )

    if window == "mid":
        score *= 0.8

    bullish_probability = _sigmoid(score)
    bearish_probability = _sigmoid(-score)
    neutral_probability = max(0.0, 1.0 - max(bullish_probability, bearish_probability))
    prob_total = bullish_probability + bearish_probability + neutral_probability
    bullish_probability /= prob_total
    bearish_probability /= prob_total
    neutral_probability /= prob_total

    if bullish_probability >= bearish_probability and bullish_probability >= neutral_probability:
        bias = "bullish"
        confidence = bullish_probability
    elif bearish_probability >= bullish_probability and bearish_probability >= neutral_probability:
        bias = "bearish"
        confidence = bearish_probability
    else:
        bias = "neutral"
        confidence = neutral_probability

    strikes = sorted(
        {round(_contract_strike(c), 2) for c in (*calls, *puts) if _contract_oi(c) > 0}
    )
    around_spot = sorted(strikes, key=lambda s: abs(s - underlying))[:3] if strikes else []

    signals = [
        {
            "name": "Call Open Interest Share",
            "value": round(call_oi_ratio, 3),
            "direction": (
                "bullish"
                if call_oi_ratio >= 0.52
                else "bearish" if call_oi_ratio <= 0.45 else "neutral"
            ),
            "explanation": (
                "A larger share of call OI points to aggregate upside interest "
                "in the chain — sometimes consistent with sizable call interest, "
                "but not exclusive to any one player."
            ),
        },
        {
            "name": "Put/Call OI Ratio",
            "value": round(put_call_oi_ratio, 3),
            "direction": (
                "bearish"
                if put_call_oi_ratio >= 1.1
                else "bullish" if put_call_oi_ratio <= 0.9 else "neutral"
            ),
            "explanation": (
                "Elevated put/call OI can indicate hedging pressure or defensive positioning."
            ),
        },
        {
            "name": "Intraday Options Flow (Calls Share)",
            "value": round(call_flow_ratio, 3),
            "direction": (
                "bullish"
                if call_flow_ratio >= 0.53
                else "bearish" if call_flow_ratio <= 0.47 else "neutral"
            ),
            "explanation": "Call-heavy volume relative to puts may indicate bullish tactical flow.",
        },
        {
            "name": "Gamma Tilt",
            "value": round(gamma_tilt, 3),
            "direction": (
                "bullish" if gamma_tilt > 0.05 else "bearish" if gamma_tilt < -0.05 else "neutral"
            ),
            "explanation": "Positive gamma tilt can support stabilization and upside continuation.",
        },
    ]

    sorted_exp = _sorted_expirations(chain, calls, puts)
    near_exps = _nearest_expirations(sorted_exp, 2)
    nearest_exp = near_exps[0] if near_exps else None
    second_exp = near_exps[1] if len(near_exps) > 1 else None

    all_iv_samples = [
        _contract_iv_pct(c)
        for c in (*calls, *puts)
        if _contract_iv_pct(c) > 0 and (_contract_oi(c) + _contract_vol(c)) > 0
    ]

    vol_sigs, vol_partial = _compute_volatility_signals(
        calls, puts, nearest_exp, underlying, all_iv_samples
    )
    near_atm = float(vol_partial.get("atm_iv") or 0.0)
    surface_sigs, surface_partial = _compute_surface_signals(
        calls, puts, nearest_exp, second_exp, underlying, near_atm
    )

    iv_rank_val = float(vol_partial.get("iv_rank") or 0.5)
    volatility_category: list[dict[str, Any]]
    if len(vol_sigs) >= 2:
        atm_row = vol_sigs[0]
        volatility_category = [
            {
                "name": "ATM Implied Volatility · IV Rank",
                "value": float(atm_row.get("value") or 0.0),
                "direction": atm_row.get("direction", "neutral"),
                "explanation": (
                    f"ATM IV is {float(atm_row.get('value') or 0.0):.2f}% (percentage points). "
                    f"Intra-chain IV rank {iv_rank_val:.0%} — how that ATM print ranks versus "
                    f"all implied volatilities in this snapshot."
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
    }

    flow_sigs = _compute_flow_signals(calls, puts)
    gamma_sigs, _net_g, regime, regime_explanation = _compute_gamma_regime(calls, puts, underlying)

    max_pain_strike = _compute_max_pain(calls, puts, nearest_exp)
    implied_move_pct, implied_move_abs = _compute_implied_move(calls, puts, nearest_exp, underlying)
    oi_clusters = _oi_clusters_by_strike(calls, puts, nearest_exp)

    max_pain_val = float(max_pain_strike) if max_pain_strike is not None else 0.0

    structure_sigs = [
        {
            "name": "Max Pain Strike",
            "value": round(max_pain_val, 4) if max_pain_strike else 0.0,
            "direction": "neutral",
            "explanation": (
                "Strike that minimizes total intrinsic value paid to option holders at expiration "
                "(nearest expiry only) — a common magnet narrative, not a forecast."
            ),
        },
        {
            "name": "Strike Magnets (OI)",
            "value": float(len(oi_clusters)),
            "direction": "neutral",
            "explanation": (
                "Largest open-interest strikes in the nearest expiration — where inventory tends to cluster."
            ),
        },
        {
            "name": "Implied Move (Straddle)",
            "value": implied_move_pct,
            "direction": "neutral",
            "explanation": (
                "ATM straddle mid / spot for the nearest expiration — a rough implied one-standard-deviation "
                "range proxy."
            ),
        },
    ]

    signal_categories = {
        "positioning": signals,
        "volatility": volatility_category,
        "flow": flow_sigs,
        "gamma": gamma_sigs,
        "structure": structure_sigs,
    }

    return {
        "symbol": symbol,
        "window": window,
        "confidence": round(confidence, 4),
        "market_bias": bias,
        "bullish_probability": round(bullish_probability, 4),
        "bearish_probability": round(bearish_probability, 4),
        "neutral_probability": round(neutral_probability, 4),
        "key_levels": around_spot,
        "analyst_summary": _build_analyst_summary(symbol, bias, confidence, window),
        "signals": signals,
        "signal_categories": signal_categories,
        "regime": regime,
        "regime_explanation": regime_explanation,
        "iv_metrics": iv_metrics,
        "max_pain": max_pain_val if max_pain_strike is not None else None,
        "implied_move": implied_move_pct,
        "implied_move_absolute": implied_move_abs,
        "oi_clusters": oi_clusters,
        "scenarios": [
            {
                "label": "Bullish continuation",
                "probability": round(bullish_probability, 4),
                "narrative": (
                    f"Upside continuation if {symbol} holds above " f"option-supported levels."
                ),
            },
            {
                "label": "Bearish unwind",
                "probability": round(bearish_probability, 4),
                "narrative": (
                    f"Downside pressure if hedging demand rises and calls unwind " f"in {symbol}."
                ),
            },
            {
                "label": "Range-bound",
                "probability": round(neutral_probability, 4),
                "narrative": "Mean-reverting regime likely if neither side gains flow dominance.",
            },
        ],
    }


async def compute_options_positioning_context(
    provider: MarketDataProvider,
    symbol: str,
    window: Literal["near", "mid"] = "near",
) -> OptionsPositioningResult:
    """Fetch quote + full chain and compute aggregate options-intelligence metrics."""
    sym = symbol.strip().upper()
    quote = await provider.get_quote(sym) or {}
    chain = await provider.get_options_chain(underlying_symbol=sym, expiration_date=None)
    calls = list(chain.calls or [])
    puts = list(chain.puts or [])
    raw = build_options_positioning_dict(chain, calls, puts, quote, sym, window)
    return OptionsPositioningResult.model_validate(raw)
