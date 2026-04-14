"""OI clusters by strike and max-pain strike."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from copinance_os.data.analytics.options.positioning.contracts import (
    contract_oi,
    contract_strike,
    contracts_for_expiration,
)
from copinance_os.domain.models.market import OptionContract
from copinance_os.domain.models.methodology import MethodologySpec


@dataclass(frozen=True, slots=True)
class OiClustersConfig:
    top_n: int = 8


DEFAULT_OI_CLUSTERS_CONFIG = OiClustersConfig()


def oi_clusters_methodology(config: OiClustersConfig) -> MethodologySpec:
    return MethodologySpec(
        id="options.positioning.oi_clusters",
        version="v1",
        model_family="strike_oi_ranking_and_max_pain",
        assumptions=("Max pain minimizes total intrinsic value weighted by OI at one expiry.",),
        limitations=("Max pain is a static snapshot heuristic.",),
        references=(),
        parameters={"top_n": str(config.top_n)},
    )


def oi_clusters_by_strike(
    calls: list[OptionContract],
    puts: list[OptionContract],
    nearest_exp: str | None,
    top_n: int = 8,
) -> list[dict[str, float]]:
    if not nearest_exp:
        return []
    oi_by: dict[float, int] = defaultdict(int)
    for c in contracts_for_expiration(calls, nearest_exp):
        oi = contract_oi(c)
        if oi is None or oi <= 0:
            continue
        oi_by[contract_strike(c)] += oi
    for p in contracts_for_expiration(puts, nearest_exp):
        oi = contract_oi(p)
        if oi is None or oi <= 0:
            continue
        oi_by[contract_strike(p)] += oi
    ranked = sorted(oi_by.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    return [{"strike": float(k), "open_interest": float(v)} for k, v in ranked if v > 0]


def oi_clusters_enhanced(
    calls: list[OptionContract],
    puts: list[OptionContract],
    nearest_exp: str | None,
    top_n: int = 8,
) -> dict[str, Any]:
    if not nearest_exp:
        return {"clusters": [], "call_wall": None, "put_wall": None}
    call_by: dict[float, int] = defaultdict(int)
    put_by: dict[float, int] = defaultdict(int)
    for c in contracts_for_expiration(calls, nearest_exp):
        oi = contract_oi(c)
        if oi is None or oi <= 0:
            continue
        call_by[contract_strike(c)] += oi
    for p in contracts_for_expiration(puts, nearest_exp):
        oi = contract_oi(p)
        if oi is None or oi <= 0:
            continue
        put_by[contract_strike(p)] += oi
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


def compute_max_pain(
    calls: list[OptionContract], puts: list[OptionContract], nearest_exp: str | None
) -> float | None:
    if not nearest_exp:
        return None
    c_exp = contracts_for_expiration(calls, nearest_exp)
    p_exp = contracts_for_expiration(puts, nearest_exp)
    strikes_set = {contract_strike(c) for c in c_exp} | {contract_strike(p) for p in p_exp}
    strikes = sorted(s for s in strikes_set if s > 0)
    if not strikes:
        return None

    def intrinsic_at(spot: float) -> float:
        total = 0.0
        for c in c_exp:
            k = contract_strike(c)
            oi = contract_oi(c)
            if oi is None or oi <= 0:
                continue
            total += max(0.0, spot - k) * oi * 100.0
        for p in p_exp:
            k = contract_strike(p)
            oi = contract_oi(p)
            if oi is None or oi <= 0:
                continue
            total += max(0.0, k - spot) * oi * 100.0
        return total

    return min(strikes, key=lambda s: intrinsic_at(s))
