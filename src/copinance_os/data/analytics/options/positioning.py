"""Core computation for options surface positioning (ported from Copinance backend).

Aggregate metrics below combine chain inputs with per-contract Greeks (often from
``quantlib_bsm_greeks``). Narrative copy for signals lives in
``data/literacy/options_positioning.py``.

Additional methodology touchpoints for newer aggregates:

- **Vanna exposure** (OI-weighted, dealer-style sign): spot–vol hedging flows;
  Bergomi (2005); institutional desk framing analogous to SqueezeMetrics-style GEX.
- **Charm exposure**: overnight delta drift from calendar time; Taleb (1997)
  *Dynamic Hedging*.
- **Mispricing** (mid vs BSM NPV): De Fontnouvelle et al. (2003).
- **Moneyness buckets** (delta bands): OCC-style surface splits; Lakonishok et al.
  (2007) for institutional flow / positioning context.
- **Pin risk** (short-dated, OI × P(ITM) heuristic): Avellaneda & Lipkin (2003).
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any, Literal, cast

from copinance_os.data.analytics.options.contract_numeric import contract_numeric
from copinance_os.data.analytics.options.quantlib_bsm_greeks import (
    enrich_options_chain_missing_greeks,
)
from copinance_os.data.literacy import options_positioning as _pt
from copinance_os.domain.literacy import resolve_financial_literacy
from copinance_os.domain.models.market import OptionContract, OptionsChain
from copinance_os.domain.models.options_positioning import (
    OptionsPositioningResult,
    SignalAgreement,
)
from copinance_os.domain.models.profile import AnalysisProfile, FinancialLiteracy
from copinance_os.domain.ports.data_providers import MarketDataProvider

# Bias model (transparent weights + normalization ranges). Narrative refs in
# ``data/literacy/options_positioning.py``: dollar inputs → Bollen & Whaley (2004), Pan & Poteshman
# (2006); net delta → Lakonishok, Lee & Poteshman (2007) / OCC-style DEX; surface skew/butterfly →
# Carr & Wu (2009), Bates (2000); implied vol from straddle → Brenner & Subrahmanyam (1988);
# GEX / flip → SqueezeMetrics-style dealer gamma, Knuteson (2021, arXiv:2006.00975).
# Vanna / charm / mispricing / pin → see module docstring above.
_BIAS_RANGES: dict[str, tuple[float, float]] = {
    "call_oi_ratio": (0.35, 0.65),
    "call_flow_share": (0.35, 0.65),
    "gamma_tilt": (-0.4, 0.4),
    "put_call_oi_ratio": (0.7, 1.6),
    "dollar_put_call_oi_ratio": (0.7, 1.6),
    "net_delta": (-500_000.0, 500_000.0),
}
_BIAS_WEIGHTS: dict[str, float] = {
    "call_oi_ratio": 1.8,
    "call_flow_share": 1.6,
    "gamma_tilt": 1.4,
    "put_call_oi_ratio": -1.2,
    "dollar_put_call_oi_ratio": -1.4,
    "net_delta": 1.2,
}

_POSITIONING_METHOD_REFERENCES: tuple[dict[str, str], ...] = (
    {
        "id": "REF_BERGOMI_2005",
        "title": "Lorenzo Bergomi (2005), Smile Dynamics IV",
        "url": "https://www.risk.net/derivatives/equity-derivatives/1510166/smile-dynamics",
    },
    {
        "id": "REF_TALEB_1997",
        "title": "Nassim Nicholas Taleb (1997), Dynamic Hedging",
        "url": "https://onlinelibrary.wiley.com/doi/book/10.1002/9781119198665",
    },
    {
        "id": "REF_CARR_WU_2009",
        "title": "Carr and Wu (2009), Variance Risk Premiums",
        "url": "https://doi.org/10.1093/rfs/hhp063",
    },
    {
        "id": "REF_DE_FONTNOUVELLE_2003",
        "title": "De Fontnouvelle et al. (2003), Option Mispricing",
        "url": "https://www.nber.org/papers/w9333",
    },
    {
        "id": "REF_AVELLANEDA_LIPKIN_2003",
        "title": "Avellaneda and Lipkin (2003), Pin Risk and Probability Models",
        "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=436260",
    },
)


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


def _contract_mid_price(c: OptionContract) -> float:
    bid, ask = _contract_bid_ask(c)
    if bid > 0 or ask > 0:
        mid = (bid + ask) / 2.0 if ask >= bid else max(bid, ask)
        if mid > 0:
            return mid
    last = _safe_float(getattr(c, "last_price", None))
    return last if last > 0 else 0.0


def _parse_expiration_to_date(exp: str) -> date | None:
    exp = exp.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(exp, fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(exp)
    except ValueError:
        return None


def _compute_data_quality(
    calls: list[OptionContract], puts: list[OptionContract], underlying: float
) -> float:
    contracts = [*calls, *puts]
    if not contracts:
        return 0.0
    n = len(contracts)
    greeks_ok = sum(1 for c in contracts if c.greeks is not None)
    greeks_coverage = greeks_ok / n
    iv_ok = sum(1 for c in contracts if _contract_iv_pct(c) > 0)
    iv_coverage = iv_ok / n

    tight_vals: list[float] = []
    for c in contracts:
        bid, ask = _contract_bid_ask(c)
        mid = (bid + ask) / 2.0 if ask >= bid and (bid > 0 or ask > 0) else 0.0
        if mid > 0:
            spread_ratio = (ask - bid) / mid
            tight_vals.append(max(0.0, min(1.0, 1.0 - spread_ratio)))
    spread_tightness = sum(tight_vals) / len(tight_vals) if tight_vals else 0.0

    total_oi = sum(_contract_oi(c) for c in contracts)
    oi_depth = min(1.0, total_oi / 10_000.0)

    active_strikes = len(
        {
            round(_contract_strike(c), 6)
            for c in contracts
            if _contract_oi(c) > 0 or _contract_vol(c) > 0
        }
    )
    strike_breadth = min(1.0, active_strikes / 20.0)

    return float(
        0.30 * greeks_coverage
        + 0.20 * iv_coverage
        + 0.20 * spread_tightness
        + 0.15 * oi_depth
        + 0.15 * strike_breadth
    )


def _compute_dollar_metrics(
    calls: list[OptionContract], puts: list[OptionContract]
) -> dict[str, float]:
    dollar_call_oi = sum(_contract_mid_price(c) * float(_contract_oi(c)) * 100.0 for c in calls)
    dollar_put_oi = sum(_contract_mid_price(p) * float(_contract_oi(p)) * 100.0 for p in puts)
    dollar_call_vol = sum(_contract_mid_price(c) * float(_contract_vol(c)) * 100.0 for c in calls)
    dollar_put_vol = sum(_contract_mid_price(p) * float(_contract_vol(p)) * 100.0 for p in puts)
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


def _compute_delta_exposure(
    calls: list[OptionContract], puts: list[OptionContract], underlying: float
) -> dict[str, float]:
    call_dex = sum(contract_numeric(c, "delta") * float(_contract_oi(c)) * 100.0 for c in calls)
    put_dex = sum(contract_numeric(p, "delta") * float(_contract_oi(p)) * 100.0 for p in puts)
    net_delta = call_dex + put_dex
    return {
        "net_delta": net_delta,
        "dollar_delta": net_delta * underlying,
        "call_delta_exposure": call_dex,
        "put_delta_exposure": put_dex,
    }


def _compute_gex_profile(
    calls: list[OptionContract],
    puts: list[OptionContract],
    nearest_exp: str | None,
    underlying: float,
) -> dict[str, Any]:
    if not nearest_exp or underlying <= 0:
        return {
            "gamma_flip_strike": None,
            "gex_profile": [],
            "top_positive_gex": [],
            "top_negative_gex": [],
        }
    mult = 100.0 * underlying
    strike_to_net: dict[float, float] = defaultdict(float)
    for c in _contracts_for_expiration(calls, nearest_exp):
        g = contract_numeric(c, "gamma")
        oi = _contract_oi(c)
        strike_to_net[_contract_strike(c)] += g * float(oi) * mult
    for p in _contracts_for_expiration(puts, nearest_exp):
        g = contract_numeric(p, "gamma")
        oi = _contract_oi(p)
        strike_to_net[_contract_strike(p)] -= g * float(oi) * mult

    if not strike_to_net:
        return {
            "gamma_flip_strike": None,
            "gex_profile": [],
            "top_positive_gex": [],
            "top_negative_gex": [],
        }

    if not any(abs(v) > 1e-9 for v in strike_to_net.values()):
        return {
            "gamma_flip_strike": None,
            "gex_profile": [],
            "top_positive_gex": [],
            "top_negative_gex": [],
        }

    strikes_sorted = sorted(strike_to_net.keys())
    per_strike = [(k, strike_to_net[k]) for k in strikes_sorted]

    gamma_flip: float | None = None
    cumulative = 0.0
    for i, (k, gex_k) in enumerate(per_strike):
        next_cum = cumulative + gex_k
        if i > 0 and cumulative * next_cum < 0.0:
            k_prev, _ = per_strike[i - 1]
            span = next_cum - cumulative
            t = abs(cumulative) / max(1e-12, abs(span))
            gamma_flip = k_prev + t * (k - k_prev)
            break
        cumulative = next_cum

    ranked_abs = sorted(per_strike, key=lambda kv: abs(kv[1]), reverse=True)
    profile_cap = ranked_abs[:15]
    gex_profile = [{"strike": float(k), "gex_value": round(v, 4)} for k, v in profile_cap]

    pos_sorted = sorted((kv for kv in per_strike if kv[1] > 0), key=lambda kv: kv[1], reverse=True)[
        :5
    ]
    neg_sorted = sorted((kv for kv in per_strike if kv[1] < 0), key=lambda kv: kv[1])[:5]
    top_pos = [{"strike": float(k), "gex_value": round(v, 4)} for k, v in pos_sorted]
    top_neg = [{"strike": float(k), "gex_value": round(v, 4)} for k, v in neg_sorted]

    return {
        "gamma_flip_strike": round(gamma_flip, 4) if gamma_flip is not None else None,
        "gex_profile": gex_profile,
        "top_positive_gex": top_pos,
        "top_negative_gex": top_neg,
    }


def _vanna_strike_multiplier(underlying: float) -> float:
    return 100.0 * max(underlying, 1e-9)


def _vanna_regime_threshold(calls: list[OptionContract], puts: list[OptionContract]) -> float:
    gross = 0.0
    for c in calls:
        gross += abs(contract_numeric(c, "vanna")) * float(_contract_oi(c))
    for p in puts:
        gross += abs(contract_numeric(p, "vanna")) * float(_contract_oi(p))
    return max(5000.0, 0.03 * gross * 100.0)


def _charm_drift_threshold(calls: list[OptionContract], puts: list[OptionContract]) -> float:
    gross = 0.0
    for c in calls:
        gross += abs(contract_numeric(c, "charm")) * float(_contract_oi(c))
    for p in puts:
        gross += abs(contract_numeric(p, "charm")) * float(_contract_oi(p))
    return max(1e-6, 0.02 * gross * 100.0)


def _compute_vanna_exposure(
    calls: list[OptionContract],
    puts: list[OptionContract],
    nearest_exp: str | None,
    underlying: float,
) -> dict[str, Any]:
    """Front-expiry OI-weighted vanna (dealer-style call − put); flip + regime.

    Motivation: spot–vol hedging flows (Bergomi 2005); desk read similar in spirit
    to published GEX-style aggregates (Knuteson 2021).
    """
    if not nearest_exp or underlying <= 0:
        return {
            "vanna_exposure": None,
            "vanna_profile": [],
        }
    mult = _vanna_strike_multiplier(underlying)
    strike_to_net: dict[float, float] = defaultdict(float)
    call_sum = 0.0
    put_sum = 0.0
    for c in _contracts_for_expiration(calls, nearest_exp):
        v = contract_numeric(c, "vanna")
        oi = _contract_oi(c)
        strike_to_net[_contract_strike(c)] += v * float(oi) * mult
        call_sum += v * float(oi) * 100.0
    for p in _contracts_for_expiration(puts, nearest_exp):
        v = contract_numeric(p, "vanna")
        oi = _contract_oi(p)
        strike_to_net[_contract_strike(p)] -= v * float(oi) * mult
        put_sum += v * float(oi) * 100.0

    if not strike_to_net or not any(abs(v) > 1e-9 for v in strike_to_net.values()):
        net_plain = call_sum - put_sum
        thr = _vanna_regime_threshold(
            _contracts_for_expiration(calls, nearest_exp),
            _contracts_for_expiration(puts, nearest_exp),
        )
        regime = (
            "short_vanna" if net_plain < -thr else "long_vanna" if net_plain > thr else "neutral"
        )
        return {
            "vanna_exposure": {
                "net_vanna": round(net_plain, 4),
                "call_vanna_exposure": round(call_sum, 4),
                "put_vanna_exposure": round(put_sum, 4),
                "vanna_flip_strike": None,
                "regime": regime,
            },
            "vanna_profile": [],
        }

    strikes_sorted = sorted(strike_to_net.keys())
    per_strike = [(k, strike_to_net[k]) for k in strikes_sorted]

    vanna_flip: float | None = None
    cumulative = 0.0
    for i, (k, vx_k) in enumerate(per_strike):
        next_cum = cumulative + vx_k
        if i > 0 and cumulative * next_cum < 0.0:
            k_prev, _ = per_strike[i - 1]
            span = next_cum - cumulative
            t = abs(cumulative) / max(1e-12, abs(span))
            vanna_flip = k_prev + t * (k - k_prev)
            break
        cumulative = next_cum

    ranked_abs = sorted(per_strike, key=lambda kv: abs(kv[1]), reverse=True)
    profile_cap = ranked_abs[:15]
    vanna_profile = [{"strike": float(k), "vanna_exposure": round(v, 4)} for k, v in profile_cap]

    net_plain = call_sum - put_sum
    c_near = _contracts_for_expiration(calls, nearest_exp)
    p_near = _contracts_for_expiration(puts, nearest_exp)
    thr = _vanna_regime_threshold(c_near, p_near)
    regime = "short_vanna" if net_plain < -thr else "long_vanna" if net_plain > thr else "neutral"

    return {
        "vanna_exposure": {
            "net_vanna": round(net_plain, 4),
            "call_vanna_exposure": round(call_sum, 4),
            "put_vanna_exposure": round(put_sum, 4),
            "vanna_flip_strike": round(vanna_flip, 4) if vanna_flip is not None else None,
            "regime": regime,
        },
        "vanna_profile": vanna_profile,
    }


def _compute_charm_exposure(
    calls: list[OptionContract], puts: list[OptionContract]
) -> dict[str, Any]:
    """OI-weighted charm (∂Δ/∂τ); overnight drift label.

    See Taleb (1997) *Dynamic Hedging* for charm / time decay of delta in practice.
    """
    call_sum = sum(contract_numeric(c, "charm") * float(_contract_oi(c)) * 100.0 for c in calls)
    put_sum = sum(contract_numeric(p, "charm") * float(_contract_oi(p)) * 100.0 for p in puts)
    net_charm = call_sum + put_sum
    thr = _charm_drift_threshold(calls, puts)
    if net_charm > thr:
        drift = "selling_pressure"
    elif net_charm < -thr:
        drift = "buying_pressure"
    else:
        drift = "neutral"
    return {
        "charm_exposure": {
            "net_charm": round(net_charm, 4),
            "call_charm_exposure": round(call_sum, 4),
            "put_charm_exposure": round(put_sum, 4),
            "overnight_delta_drift": drift,
        }
    }


def _compute_mispricing(
    calls: list[OptionContract],
    puts: list[OptionContract],
) -> dict[str, Any] | None:
    """Mid vs BSM NPV at quoted IV by side; heuristic sentiment.

    Related empirical framing: De Fontnouvelle et al. (2003).
    """
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
        mid = _contract_mid_price(contract)
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
        mid = _contract_mid_price(contract)
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
    if call_avg > 2.0 and put_avg < 1.0:
        sentiment = "call_demand"
    elif put_avg > 2.0 and call_avg < 1.0:
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


def _moneyness_bucket_name(abs_delta: float) -> str:
    if abs_delta > 0.9:
        return "deep_itm"
    if abs_delta > 0.7:
        return "itm"
    if abs_delta > 0.4:
        return "atm"
    if abs_delta > 0.1:
        return "otm"
    return "deep_otm"


def _moneyness_flow_direction(
    dominant_call: str | None, dominant_put: str | None
) -> Literal["bullish", "bearish", "neutral"]:
    wing_c = dominant_call in ("deep_otm", "otm")
    wing_p = dominant_put in ("deep_otm", "otm")
    if wing_c and not wing_p:
        return "bullish"
    if wing_p and not wing_c:
        return "bearish"
    return "neutral"


def _compute_moneyness_buckets(
    calls: list[OptionContract],
    puts: list[OptionContract],
) -> dict[str, Any]:
    """Delta-bucketed OI and dollar volume (OCC-style moneyness split).

    Institutional flow decomposition context: Lakonishok et al. (2007).
    """
    order = ["deep_itm", "itm", "atm", "otm", "deep_otm"]
    acc: dict[str, dict[str, int | float]] = {
        b: {
            "call_oi": 0,
            "put_oi": 0,
            "call_volume": 0,
            "put_volume": 0,
            "dollar_call_volume": 0.0,
            "dollar_put_volume": 0.0,
        }
        for b in order
    }

    def _add(contract: OptionContract, side: Literal["call", "put"]) -> None:
        if contract.greeks is None:
            return
        d = abs(float(contract.greeks.delta))
        bname = _moneyness_bucket_name(d)
        row = acc[bname]
        oi = _contract_oi(contract)
        vol = _contract_vol(contract)
        mid = _contract_mid_price(contract)
        dv = float(vol) * mid * 100.0
        if side == "call":
            row["call_oi"] = int(row["call_oi"]) + oi
            row["call_volume"] = int(row["call_volume"]) + vol
            row["dollar_call_volume"] = float(row["dollar_call_volume"]) + dv
        else:
            row["put_oi"] = int(row["put_oi"]) + oi
            row["put_volume"] = int(row["put_volume"]) + vol
            row["dollar_put_volume"] = float(row["dollar_put_volume"]) + dv

    for c in calls:
        _add(c, "call")
    for p in puts:
        _add(p, "put")

    buckets_out = [
        {
            "bucket": b,
            "call_oi": int(acc[b]["call_oi"]),
            "put_oi": int(acc[b]["put_oi"]),
            "call_volume": int(acc[b]["call_volume"]),
            "put_volume": int(acc[b]["put_volume"]),
            "dollar_call_volume": round(float(acc[b]["dollar_call_volume"]), 4),
            "dollar_put_volume": round(float(acc[b]["dollar_put_volume"]), 4),
        }
        for b in order
    ]

    def _dominant(side: Literal["call", "put"]) -> str | None:
        best_b: str | None = None
        best_v = -1.0
        for b in order:
            key = "dollar_call_volume" if side == "call" else "dollar_put_volume"
            v = float(acc[b][key])
            if v > best_v:
                best_v = v
                best_b = b
        return best_b if best_v > 0 else None

    return {
        "moneyness_summary": {
            "buckets": buckets_out,
            "dominant_call_bucket": _dominant("call"),
            "dominant_put_bucket": _dominant("put"),
        }
    }


def _compute_pin_risk(
    calls: list[OptionContract],
    puts: list[OptionContract],
    nearest_exp: str | None,
    underlying: float,
    as_of_date: date,
) -> dict[str, Any] | None:
    """Short-dated pin heuristic: OI × QuantLib P(ITM) vs volume; Avellaneda & Lipkin (2003)."""
    if not nearest_exp or underlying <= 0:
        return None
    exp_d = _parse_expiration_to_date(nearest_exp)
    if exp_d is None:
        return None
    dte = (exp_d - as_of_date).days
    if dte > 5:
        return None

    total_vol = sum(_contract_vol(c) for c in calls) + sum(_contract_vol(p) for p in puts)

    calls_by_k: dict[float, list[OptionContract]] = defaultdict(list)
    puts_by_k: dict[float, list[OptionContract]] = defaultdict(list)
    for c in _contracts_for_expiration(calls, nearest_exp):
        calls_by_k[_contract_strike(c)].append(c)
    for p in _contracts_for_expiration(puts, nearest_exp):
        puts_by_k[_contract_strike(p)].append(p)

    def _weighted_itm(contracts: list[OptionContract]) -> float | None:
        num = 0.0
        den = 0
        for c in contracts:
            if c.greeks is None or c.greeks.itm_probability is None:
                continue
            oi = _contract_oi(c)
            if oi <= 0:
                continue
            num += float(c.greeks.itm_probability) * oi
            den += oi
        if den <= 0:
            return None
        return num / den

    strikes_set = set(calls_by_k.keys()) | set(puts_by_k.keys())
    rows: list[tuple[float, int, float, float]] = []
    for k in strikes_set:
        call_oi = sum(_contract_oi(c) for c in calls_by_k.get(k, ()))
        put_oi = sum(_contract_oi(p) for p in puts_by_k.get(k, ()))
        total_oi = call_oi + put_oi
        if total_oi <= 1000:
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
        pin_score = min(1.0, flow_ratio * 6.0) * (1.0 / (1.0 + 4.0 * rel))
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
    max_score = max_row[3]
    if dte <= 2 and max_score > 0.7:
        level = "high"
    elif dte <= 5 and max_score > 0.4:
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
    lit: FinancialLiteracy,
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
                    "name": _pt.name_atm_iv(lit),
                    "value": 0.0,
                    "direction": "neutral",
                    "explanation": _pt.expl_iv_no_quotes_near_money(lit),
                },
                {
                    "name": _pt.name_iv_rank(lit),
                    "value": round(_percentile_rank(0.0, all_iv_samples), 4),
                    "direction": "neutral",
                    "explanation": _pt.expl_iv_rank_degenerate(lit),
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


def _compute_surface_signals(
    calls: list[OptionContract],
    puts: list[OptionContract],
    nearest_exp: str | None,
    second_exp: str | None,
    underlying: float,
    near_atm_iv: float,
    lit: FinancialLiteracy,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    skew_val = 0.0
    skew_expl = _pt.expl_skew_insufficient(lit)
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
            skew_expl = _pt.expl_skew_ok(lit)

        skew_10_val = None
        butterfly_25 = None
        skew_regime: Literal["steep_put", "normal", "call_skewed"] | None = None
        if c_candidates:
            call_10 = min(c_candidates, key=lambda c: abs(contract_numeric(c, "delta") - 0.10))
            call_10_iv = _contract_iv_pct(call_10)
        else:
            call_10 = None
            call_10_iv = 0.0
        if p_candidates:
            put_10 = min(p_candidates, key=lambda p: abs(contract_numeric(p, "delta") + 0.10))
            put_10_iv = _contract_iv_pct(put_10)
        else:
            put_10 = None
            put_10_iv = 0.0
        if call_10 is not None and put_10 is not None:
            skew_10_val = round(put_10_iv - call_10_iv, 4)
        if call_25 is not None and put_25 is not None:
            butterfly_25 = round((put_iv + call_iv) / 2.0 - near_atm_iv, 4)
        if skew_val > 3.0:
            skew_regime = "steep_put"
        elif skew_val < -1.5:
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
                slope_expl = _pt.expl_term_move(lit, near_atm_iv, far_atm_iv, slope)

    skew_dir: Literal["bullish", "bearish", "neutral"] = (
        "bearish" if skew_val > 2.0 else "bullish" if skew_val < -1.0 else "neutral"
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


def _compute_flow_signals(
    calls: list[OptionContract], puts: list[OptionContract], lit: FinancialLiteracy
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
            "name": _pt.name_unusual_activity(lit),
            "value": unusual_score,
            "direction": unusual_dir,
            "explanation": _pt.expl_unusual_activity(lit, vol_threshold),
        },
        {
            "name": _pt.name_agg_vol_oi(lit),
            "value": round(agg_ratio, 4),
            "direction": flow_dir,
            "explanation": _pt.expl_agg_vol_oi(lit),
        },
    ]


def _compute_gamma_regime(
    calls: list[OptionContract],
    puts: list[OptionContract],
    underlying: float,
    lit: FinancialLiteracy,
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
        expl = _pt.expl_gamma_neutral_flat(lit)
    else:
        rel = net / gross
        if rel > 0.06:
            regime = "positive_gamma"
            expl = _pt.expl_gamma_positive(lit)
        elif rel < -0.06:
            regime = "negative_gamma"
            expl = _pt.expl_gamma_negative(lit)
        else:
            regime = "neutral"
            expl = _pt.expl_gamma_balanced(lit)

    net_rounded = round(net, 4)
    signals = [
        {
            "name": _pt.name_net_gamma(lit),
            "value": net_rounded,
            "direction": "bullish" if net > 0 else "bearish" if net < 0 else "neutral",
            "explanation": _pt.expl_net_gamma(lit),
        },
        {
            "name": _pt.name_gamma_regime(lit),
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


def _oi_clusters_enhanced(
    calls: list[OptionContract], puts: list[OptionContract], nearest_exp: str | None, top_n: int = 8
) -> dict[str, Any]:
    if not nearest_exp:
        return {"clusters": [], "call_wall": None, "put_wall": None}
    call_by: dict[float, int] = defaultdict(int)
    put_by: dict[float, int] = defaultdict(int)
    for c in _contracts_for_expiration(calls, nearest_exp):
        call_by[_contract_strike(c)] += _contract_oi(c)
    for p in _contracts_for_expiration(puts, nearest_exp):
        put_by[_contract_strike(p)] += _contract_oi(p)
    merged: dict[float, tuple[int, int]] = {}
    for k, v in call_by.items():
        merged[k] = (v, put_by.get(k, 0))
    for k, v in put_by.items():
        if k not in merged:
            merged[k] = (call_by.get(k, 0), v)
    rows: list[tuple[float, int, int, int, float]] = []
    for k, (co, po) in merged.items():
        tot = co + po
        if tot <= 0:
            continue
        rows.append((k, co, po, tot, po / max(1, co)))
    rows.sort(key=lambda r: r[3], reverse=True)
    top = rows[:top_n]
    clusters = [
        {
            "strike": float(k),
            "call_oi": float(co),
            "put_oi": float(po),
            "total_oi": float(tot),
            "put_call_ratio": round(pcr, 4),
        }
        for k, co, po, tot, pcr in top
    ]
    call_wall = max(call_by, key=lambda s: call_by[s]) if call_by else None
    put_wall = max(put_by, key=lambda s: put_by[s]) if put_by else None
    return {"clusters": clusters, "call_wall": call_wall, "put_wall": put_wall}


def _compute_implied_move(
    calls: list[OptionContract],
    puts: list[OptionContract],
    nearest_exp: str | None,
    underlying: float,
    as_of_date: date,
) -> tuple[float, float, dict[str, Any] | None]:
    if not nearest_exp or underlying <= 0:
        return 0.0, 0.0, None
    c_near = _contracts_for_expiration(calls, nearest_exp)
    p_near = _contracts_for_expiration(puts, nearest_exp)
    strikes = sorted(
        {_contract_strike(c) for c in c_near if _contract_oi(c) + _contract_vol(c) > 0}
        & {_contract_strike(p) for p in p_near if _contract_oi(p) + _contract_vol(p) > 0}
    )
    atm = _atm_strike(strikes, underlying)
    if atm is None:
        return 0.0, 0.0, None
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
        return 0.0, 0.0, None
    straddle = call_mid + put_mid
    pct = (straddle / underlying) * 100.0
    exp_d = _parse_expiration_to_date(nearest_exp)
    if exp_d is None:
        return round(pct, 4), round(straddle, 4), None
    dte = max(1, (exp_d - as_of_date).days)
    t_year = dte / 365.0
    ann = (straddle / (0.798 * underlying * math.sqrt(t_year))) * 100.0
    daily = ann / math.sqrt(252.0)
    period = ann * math.sqrt(dte / 252.0)
    detail = {
        "raw_straddle_pct": round(pct, 4),
        "raw_straddle_abs": round(straddle, 4),
        "dte": dte,
        "annualized_iv": round(ann, 4),
        "daily_implied_move_pct": round(daily, 4),
        "period_implied_move_pct": round(period, 4),
    }
    return round(pct, 4), round(straddle, 4), detail


def _compute_bias_score(
    call_oi_ratio: float,
    call_flow_share: float,
    gamma_tilt: float,
    put_call_oi_ratio: float,
    dollar_put_call_oi_ratio: float,
    net_delta: float,
    dollar_call_oi: float,
) -> float:
    score = 0.0
    for key, weight in _BIAS_WEIGHTS.items():
        if key == "call_oi_ratio":
            val = call_oi_ratio
        elif key == "call_flow_share":
            val = call_flow_share
        elif key == "gamma_tilt":
            val = gamma_tilt
        elif key == "put_call_oi_ratio":
            val = put_call_oi_ratio
        elif key == "dollar_put_call_oi_ratio":
            if dollar_call_oi <= 0.0:
                continue
            val = dollar_put_call_oi_ratio
        else:
            val = net_delta
        lo, hi = _BIAS_RANGES[key]
        score += (_normalize(val, lo, hi) - 0.5) * weight
    return score


def _compute_signal_agreement(
    positioning: list[dict[str, Any]],
    flow: list[dict[str, Any]],
    gamma: list[dict[str, Any]],
) -> SignalAgreement:
    rows = [*positioning, *flow, *gamma]
    bull = sum(1 for r in rows if r.get("direction") == "bullish")
    bear = sum(1 for r in rows if r.get("direction") == "bearish")
    if bull == bear or bull + bear == 0:
        return "mixed"
    dom_bull = bull > bear
    frac = max(bull, bear) / (bull + bear)
    if frac >= 0.75:
        strength = "strong"
    elif frac >= 0.58:
        strength = "moderate"
    else:
        strength = "weak"
    if dom_bull:
        return cast(SignalAgreement, f"{strength}_bullish")
    return cast(SignalAgreement, f"{strength}_bearish")


def _build_positioning_methodology(
    *,
    symbol: str,
    window: Literal["near", "mid"],
    ref_date: date,
    nearest_exp: date | str | None,
    second_exp: date | str | None,
    data_quality: float,
) -> dict[str, Any]:
    def _exp_to_text(x: date | str | None) -> str | None:
        if x is None:
            return None
        if isinstance(x, date):
            return x.isoformat()
        return str(x)

    expiries = (
        ",".join(x for x in (_exp_to_text(nearest_exp), _exp_to_text(second_exp)) if x) or "none"
    )
    return {
        "version": "options_positioning_v2",
        "computed_at": datetime(
            ref_date.year, ref_date.month, ref_date.day, tzinfo=UTC
        ).isoformat(),
        "model_family": "aggregate_chain_heuristics_plus_bsm_enrichment",
        "assumptions": [
            "Per-contract Greeks use European BSM assumptions when enrichment is required.",
            "Aggregate directional scores combine OI, volume, IV surface, and Greeks with fixed transparent weights.",
            f"Positioning window '{window}' applies horizon damping to the aggregate bias score.",
        ],
        "limitations": [
            "Positioning signals are heuristic aggregates and not execution advice.",
            "Low liquidity or sparse strikes can reduce reliability for skew, pin, and flow metrics.",
            "BSM-based mispricing and ITM probabilities depend on quoted implied volatility quality.",
        ],
        "references": list(_POSITIONING_METHOD_REFERENCES),
        "data_inputs": {
            "symbol": symbol,
            "as_of_date": ref_date.isoformat(),
            "window": window,
            "expirations_used": expiries,
            "data_quality": f"{data_quality:.4f}",
        },
    }


def build_options_positioning_dict(
    chain: OptionsChain,
    calls: list[OptionContract],
    puts: list[OptionContract],
    quote: dict[str, Any],
    symbol: str,
    window: Literal["near", "mid"],
    financial_literacy: FinancialLiteracy | str | None = None,
    as_of_date: date | None = None,
    enrich_missing_greeks: bool = False,
    analysis_profile: AnalysisProfile | None = None,
) -> dict[str, Any]:
    """Build the full positioning payload dict (validated by ``OptionsPositioningResult``).

    ``financial_literacy`` controls plain-language depth (beginner / intermediate / advanced).
    Omitted or invalid values default to **intermediate** (legacy copy).
    ``as_of_date`` anchors DTE for implied-move de-annualization (defaults to today).
    When ``enrich_missing_greeks`` is True, rows with ``greeks is None`` are filled via
    QuantLib analytic European BSM (same assumptions as ``QuantLibBsmGreekEstimator``) before
    aggregation; vendor Greeks are not overwritten. No-op if QuantLib is unavailable.
    """
    lit = resolve_financial_literacy(financial_literacy)
    ref_date = as_of_date or date.today()
    if enrich_missing_greeks:
        merged = chain.model_copy(update={"calls": calls, "puts": puts})
        merged = enrich_options_chain_missing_greeks(
            merged, evaluation_date=ref_date, profile=analysis_profile
        )
        chain = merged
        calls = list(chain.calls or [])
        puts = list(chain.puts or [])
    up = chain.underlying_price
    underlying = _safe_float(up, _safe_float(quote.get("current_price")))

    sorted_exp = _sorted_expirations(chain, calls, puts)
    near_exps = _nearest_expirations(sorted_exp, 2)
    nearest_exp = near_exps[0] if near_exps else None
    second_exp = near_exps[1] if len(near_exps) > 1 else None

    data_quality = _compute_data_quality(calls, puts, underlying)
    dollar_metrics_dict = _compute_dollar_metrics(calls, puts)
    delta_exposure_dict = _compute_delta_exposure(calls, puts, underlying)
    gex_bundle = _compute_gex_profile(calls, puts, nearest_exp, underlying)
    oi_enhanced_bundle = _oi_clusters_enhanced(calls, puts, nearest_exp)
    vanna_bundle = _compute_vanna_exposure(calls, puts, nearest_exp, underlying)
    charm_bundle = _compute_charm_exposure(calls, puts)
    mispricing_bundle = _compute_mispricing(calls, puts)
    moneyness_bundle = _compute_moneyness_buckets(calls, puts)
    pin_bundle = _compute_pin_risk(calls, puts, nearest_exp, underlying, ref_date)

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

    dollar_tot_vol = (
        dollar_metrics_dict["dollar_call_volume"] + dollar_metrics_dict["dollar_put_volume"]
    )
    call_flow_share_score = (
        dollar_metrics_dict["dollar_call_flow_share"] if dollar_tot_vol > 0.0 else call_flow_ratio
    )

    score = _compute_bias_score(
        call_oi_ratio,
        call_flow_share_score,
        gamma_tilt,
        put_call_oi_ratio,
        dollar_metrics_dict["dollar_put_call_oi_ratio"],
        delta_exposure_dict["net_delta"],
        dollar_metrics_dict["dollar_call_oi"],
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
        bias: Literal["bullish", "bearish", "neutral"] = "bullish"
        confidence = bullish_probability
    elif bearish_probability >= bullish_probability and bearish_probability >= neutral_probability:
        bias = "bearish"
        confidence = bearish_probability
    else:
        bias = "neutral"
        confidence = neutral_probability

    confidence *= 0.5 + 0.5 * data_quality

    strikes = sorted(
        {round(_contract_strike(c), 2) for c in (*calls, *puts) if _contract_oi(c) > 0}
    )
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
        _contract_iv_pct(c)
        for c in (*calls, *puts)
        if _contract_iv_pct(c) > 0 and (_contract_oi(c) + _contract_vol(c)) > 0
    ]

    vol_sigs, vol_partial = _compute_volatility_signals(
        calls, puts, nearest_exp, underlying, all_iv_samples, lit
    )
    near_atm = float(vol_partial.get("atm_iv") or 0.0)
    surface_sigs, surface_partial = _compute_surface_signals(
        calls, puts, nearest_exp, second_exp, underlying, near_atm, lit
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

    flow_sigs = _compute_flow_signals(calls, puts, lit)
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
    mom_dir = _moneyness_flow_direction(
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

    gamma_sigs, _net_g, regime, regime_explanation = _compute_gamma_regime(
        calls, puts, underlying, lit
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

    max_pain_strike = _compute_max_pain(calls, puts, nearest_exp)
    implied_move_pct, implied_move_abs, implied_move_detail = _compute_implied_move(
        calls, puts, nearest_exp, underlying, ref_date
    )
    oi_clusters = _oi_clusters_by_strike(calls, puts, nearest_exp)

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
    signal_agreement = _compute_signal_agreement(
        signal_categories["positioning"],
        signal_categories["flow"],
        signal_categories["gamma"],
    )

    scen_bull, scen_bear, scen_range = _pt.scenario_narratives(symbol, lit)

    cw = oi_enhanced_bundle["call_wall"]
    pw = oi_enhanced_bundle["put_wall"]
    methodology = _build_positioning_methodology(
        symbol=symbol,
        window=window,
        ref_date=ref_date,
        nearest_exp=nearest_exp,
        second_exp=second_exp,
        data_quality=data_quality,
    )

    return {
        "symbol": symbol,
        "window": window,
        "methodology": methodology,
        "confidence": round(confidence, 4),
        "market_bias": bias,
        "bullish_probability": round(bullish_probability, 4),
        "bearish_probability": round(bearish_probability, 4),
        "neutral_probability": round(neutral_probability, 4),
        "key_levels": around_spot,
        "analyst_summary": _pt.analyst_summary(symbol, bias, confidence, window, lit),
        "signals": signals,
        "signal_categories": signal_categories,
        "regime": regime,
        "regime_explanation": regime_explanation,
        "iv_metrics": iv_metrics,
        "max_pain": max_pain_val if max_pain_strike is not None else None,
        "implied_move": implied_move_pct,
        "implied_move_absolute": implied_move_abs,
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
        "scenarios": [
            {
                "label": "Bullish continuation",
                "probability": round(bullish_probability, 4),
                "narrative": scen_bull,
            },
            {
                "label": "Bearish unwind",
                "probability": round(bearish_probability, 4),
                "narrative": scen_bear,
            },
            {
                "label": "Range-bound",
                "probability": round(neutral_probability, 4),
                "narrative": scen_range,
            },
        ],
    }


async def compute_options_positioning_context(
    provider: MarketDataProvider,
    symbol: str,
    window: Literal["near", "mid"] = "near",
    financial_literacy: FinancialLiteracy | str | None = None,
) -> OptionsPositioningResult:
    """Fetch quote + full chain and compute aggregate options-intelligence metrics."""
    sym = symbol.strip().upper()
    quote = await provider.get_quote(sym) or {}
    chain = await provider.get_options_chain(underlying_symbol=sym, expiration_date=None)
    calls = list(chain.calls or [])
    puts = list(chain.puts or [])
    raw = build_options_positioning_dict(
        chain,
        calls,
        puts,
        quote,
        sym,
        window,
        financial_literacy=financial_literacy,
        enrich_missing_greeks=True,
    )
    return OptionsPositioningResult.model_validate(raw)
