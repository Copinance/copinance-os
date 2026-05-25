"""Deterministic, size-capped summaries for curated-questions LLM prompts."""

from __future__ import annotations

import json
import math
from collections import Counter
from typing import Any

from copinance_os.data.curated_questions.limits import ARTIFACT_MAX_JSON_CHARS
from copinance_os.domain.models.curated_questions import ArtifactType


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _truncate_json_dict(data: dict[str, Any], max_chars: int) -> dict[str, Any]:
    serialized = json.dumps(data, default=str)
    if len(serialized) <= max_chars:
        return data
    trimmed = dict(data)
    for key in ("contracts_preview", "top_oi_strikes", "indicators", "sectors", "events", "items"):
        if key in trimmed and isinstance(trimmed[key], list) and len(trimmed[key]) > 3:
            trimmed[key] = trimmed[key][:3]
            serialized = json.dumps(trimmed, default=str)
            if len(serialized) <= max_chars:
                return trimmed
    if len(serialized) > max_chars:
        trimmed["_truncated"] = True
        trimmed["_note"] = "summary truncated for token budget"
    return trimmed


def cap_context_for_artifact(artifact: ArtifactType, context: dict[str, Any]) -> dict[str, Any]:
    max_chars = ARTIFACT_MAX_JSON_CHARS.get(artifact, 4_000)
    return _truncate_json_dict(context, max_chars)


def build_context(artifact: ArtifactType, validated_payload: dict[str, Any]) -> dict[str, Any]:
    """Build artifact-specific summary dict from validated payload."""
    builders = {
        ArtifactType.OPTIONS_CHAIN: build_options_chain_context,
        ArtifactType.QUOTE: build_quote_context,
        ArtifactType.HISTORICAL_BARS: build_historical_bars_context,
        ArtifactType.INSTRUMENT: build_instrument_context,
        ArtifactType.FUNDAMENTALS: build_fundamentals_context,
        ArtifactType.MARKET_REGIME: build_market_regime_context,
        ArtifactType.MACRO_SNAPSHOT: build_macro_snapshot_context,
        ArtifactType.SECTOR_ROTATION: build_sector_rotation_context,
        ArtifactType.UPCOMING_EVENTS: build_upcoming_events_context,
        ArtifactType.WATCHLIST_RISK: build_watchlist_risk_context,
        ArtifactType.OPTIONS_POSITIONING: build_options_positioning_context,
    }
    builder = builders[artifact]
    summary = builder(validated_payload)
    return cap_context_for_artifact(artifact, summary)


def build_options_chain_context(payload: dict[str, Any]) -> dict[str, Any]:
    calls = payload.get("calls") or []
    puts = payload.get("puts") or []
    all_contracts = [*calls, *puts]
    underlying = _safe_float(payload.get("underlying_price"))
    call_oi = sum(int(c.get("open_interest") or 0) for c in calls)
    put_oi = sum(int(p.get("open_interest") or 0) for p in puts)
    call_vol = sum(int(c.get("volume") or 0) for c in calls)
    put_vol = sum(int(p.get("volume") or 0) for p in puts)
    iv_values = [
        v
        for v in (_safe_float(c.get("implied_volatility")) for c in all_contracts)
        if v is not None
    ]

    def _oi_key(c: dict[str, Any]) -> int:
        return int(c.get("open_interest") or 0)

    top_oi = sorted(all_contracts, key=_oi_key, reverse=True)[:5]
    top_oi_strikes = [
        {
            "side": c.get("side"),
            "strike": c.get("strike"),
            "open_interest": c.get("open_interest"),
            "volume": c.get("volume"),
        }
        for c in top_oi
    ]

    atm = None
    if underlying and underlying > 0 and all_contracts:

        def _strike_dist(c: dict[str, Any]) -> float:
            s = _safe_float(c.get("strike"))
            return abs((s or 0.0) - underlying)

        atm_c = min(all_contracts, key=_strike_dist)
        atm = {
            "strike": atm_c.get("strike"),
            "side": atm_c.get("side"),
            "open_interest": atm_c.get("open_interest"),
            "implied_volatility": atm_c.get("implied_volatility"),
        }

    put_call_oi = (put_oi / call_oi) if call_oi > 0 else None

    return {
        "artifact": ArtifactType.OPTIONS_CHAIN.value,
        "underlying_symbol": payload.get("underlying_symbol"),
        "expiration_date": payload.get("expiration_date"),
        "underlying_price": payload.get("underlying_price"),
        "calls_count": len(calls),
        "puts_count": len(puts),
        "total_open_interest": call_oi + put_oi,
        "total_volume": call_vol + put_vol,
        "put_call_open_interest_ratio": put_call_oi,
        "average_implied_volatility": (sum(iv_values) / len(iv_values) if iv_values else None),
        "at_the_money": atm,
        "top_oi_strikes": top_oi_strikes,
    }


def build_quote_context(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "symbol",
        "current_price",
        "previous_close",
        "open",
        "high",
        "low",
        "volume",
        "market_cap",
        "currency",
        "exchange",
        "regularMarketChangePercent",
        "fiftyTwoWeekHigh",
        "fiftyTwoWeekLow",
    )
    summary = {k: payload.get(k) for k in keys if payload.get(k) is not None}
    summary["artifact"] = ArtifactType.QUOTE.value
    if "symbol" not in summary and payload.get("symbol"):
        summary["symbol"] = payload["symbol"]
    return summary


def build_historical_bars_context(payload: dict[str, Any]) -> dict[str, Any]:
    bars = payload.get("data") or payload.get("bars") or []
    closes: list[float] = []
    for bar in bars:
        c = _safe_float(bar.get("close_price") or bar.get("close"))
        if c is not None:
            closes.append(c)
    simple_return: float | None = None
    vol: float | None = None
    if len(closes) >= 2 and closes[0] != 0:
        simple_return = (closes[-1] - closes[0]) / closes[0]
    if len(closes) >= 3:
        log_rets = [
            math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i - 1] > 0
        ]
        if log_rets:
            mean = sum(log_rets) / len(log_rets)
            var = sum((r - mean) ** 2 for r in log_rets) / len(log_rets)
            vol = math.sqrt(var) * math.sqrt(252)

    first_ts = bars[0].get("timestamp") if bars else None
    last_ts = bars[-1].get("timestamp") if bars else None

    return {
        "artifact": ArtifactType.HISTORICAL_BARS.value,
        "symbol": payload.get("symbol"),
        "interval": payload.get("interval"),
        "bar_count": len(bars),
        "first_timestamp": str(first_ts) if first_ts else None,
        "last_timestamp": str(last_ts) if last_ts else None,
        "simple_return_over_window": simple_return,
        "annualized_vol_estimate": vol,
        "last_close": closes[-1] if closes else None,
    }


def build_instrument_context(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact": ArtifactType.INSTRUMENT.value,
        "symbol": payload.get("symbol"),
        "name": payload.get("name"),
        "exchange": payload.get("exchange"),
        "sector": payload.get("sector"),
        "industry": payload.get("industry"),
        "market_cap": payload.get("market_cap"),
        "beta": payload.get("beta"),
        "currency": payload.get("currency"),
    }


def build_fundamentals_context(payload: dict[str, Any]) -> dict[str, Any]:
    ratios = payload.get("ratios") or {}
    ratio_subset = {k: ratios[k] for k in list(ratios)[:12]} if isinstance(ratios, dict) else {}
    return {
        "artifact": ArtifactType.FUNDAMENTALS.value,
        "symbol": payload.get("symbol"),
        "company_name": payload.get("company_name"),
        "sector": payload.get("sector"),
        "industry": payload.get("industry"),
        "income_statement_periods": len(payload.get("income_statements") or []),
        "balance_sheet_periods": len(payload.get("balance_sheets") or []),
        "cash_flow_periods": len(payload.get("cash_flow_statements") or []),
        "ratios": ratio_subset,
    }


def build_market_regime_context(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact": ArtifactType.MARKET_REGIME.value,
        "market_index": payload.get("market_index"),
        "trend_regime": payload.get("trend_regime") or payload.get("trend"),
        "vol_regime": payload.get("vol_regime") or payload.get("volatility_regime"),
        "confidence": payload.get("confidence"),
        "vix": payload.get("vix") or payload.get("vix_level"),
        "breadth": payload.get("breadth") or payload.get("market_breadth"),
    }


def build_macro_snapshot_context(payload: dict[str, Any]) -> dict[str, Any]:
    indicators = payload.get("indicators") or []
    preview = indicators[:8] if isinstance(indicators, list) else []
    return {
        "artifact": ArtifactType.MACRO_SNAPSHOT.value,
        "indicator_count": len(indicators) if isinstance(indicators, list) else 0,
        "indicators": preview,
    }


def build_sector_rotation_context(payload: dict[str, Any]) -> dict[str, Any]:
    sectors = payload.get("sectors") or []
    sorted_sectors = sorted(
        sectors,
        key=lambda s: _safe_float(s.get("momentum") or s.get("return") or s.get("change")) or 0.0,
        reverse=True,
    )
    top = sorted_sectors[:5]
    bottom = sorted_sectors[-3:] if len(sorted_sectors) > 3 else []
    return {
        "artifact": ArtifactType.SECTOR_ROTATION.value,
        "sector_count": len(sectors),
        "top_momentum": top,
        "bottom_momentum": bottom,
    }


def build_upcoming_events_context(payload: dict[str, Any]) -> dict[str, Any]:
    events = payload.get("events") or []
    type_counts = Counter(str(e.get("type") or e.get("event_type") or "other") for e in events)
    nearest = sorted(
        events,
        key=lambda e: str(e.get("date") or e.get("start_date") or ""),
    )[:5]
    return {
        "artifact": ArtifactType.UPCOMING_EVENTS.value,
        "event_count": len(events),
        "events_by_type": dict(type_counts),
        "nearest_events": nearest,
    }


def build_watchlist_risk_context(payload: dict[str, Any]) -> dict[str, Any]:
    items = payload.get("items") or []
    symbols = payload.get("symbols") or [str(i.get("symbol")) for i in items if i.get("symbol")]
    preview = items[:8] if items else [{"symbol": s} for s in symbols[:8]]
    return {
        "artifact": ArtifactType.WATCHLIST_RISK.value,
        "symbol_count": len(symbols),
        "symbols_sample": symbols[:10],
        "items_preview": preview,
    }


def build_options_positioning_context(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "symbol",
        "window",
        "market_bias",
        "confidence",
        "bullish_probability",
        "bearish_probability",
        "max_pain",
        "gamma_flip_strike",
        "regime",
        "iv_metrics",
        "top_positive_gex",
        "top_negative_gex",
        "oi_clusters",
        "analyst_summary",
    )
    summary = {k: payload.get(k) for k in keys if payload.get(k) is not None}
    summary["artifact"] = ArtifactType.OPTIONS_POSITIONING.value
    return summary
