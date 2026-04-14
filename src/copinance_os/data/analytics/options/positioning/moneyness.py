"""Delta-bucketed OI and dollar volume (moneyness ladder)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from copinance_os.data.analytics.options.positioning.contracts import (
    contract_mid_price,
    contract_oi,
    contract_vol,
)
from copinance_os.domain.models.market import OptionContract
from copinance_os.domain.models.methodology import MethodologySpec


@dataclass(frozen=True, slots=True)
class MoneynessConfig:
    pass


DEFAULT_MONEYNESS_CONFIG = MoneynessConfig()


def moneyness_methodology(_config: MoneynessConfig) -> MethodologySpec:
    return MethodologySpec(
        id="options.positioning.moneyness",
        version="v1",
        model_family="delta_bucket_surface",
        assumptions=("Buckets use absolute delta from ``OptionGreeks`` when present.",),
        limitations=("Vendor delta may differ from model-implied delta.",),
        references=(),
        parameters={},
    )


def moneyness_bucket_name(abs_delta: float) -> str:
    if abs_delta > 0.9:
        return "deep_itm"
    if abs_delta > 0.7:
        return "itm"
    if abs_delta > 0.4:
        return "atm"
    if abs_delta > 0.1:
        return "otm"
    return "deep_otm"


def moneyness_flow_direction(
    dominant_call: str | None, dominant_put: str | None
) -> Literal["bullish", "bearish", "neutral"]:
    wing_c = dominant_call in ("deep_otm", "otm")
    wing_p = dominant_put in ("deep_otm", "otm")
    if wing_c and not wing_p:
        return "bullish"
    if wing_p and not wing_c:
        return "bearish"
    return "neutral"


def compute_moneyness_buckets(
    calls: list[OptionContract],
    puts: list[OptionContract],
    _config: MoneynessConfig = DEFAULT_MONEYNESS_CONFIG,
) -> dict[str, Any]:
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
        bname = moneyness_bucket_name(d)
        row = acc[bname]
        oi = contract_oi(contract)
        vol = contract_vol(contract)
        mid = contract_mid_price(contract)
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
