"""Unusual volume and aggregate volume/OI flow heuristics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from copinance_os.data.analytics.options.positioning.contracts import contract_oi, contract_vol
from copinance_os.data.literacy import options_positioning as _pt
from copinance_os.domain.literacy import FinancialLiteracy
from copinance_os.domain.models.market import OptionContract
from copinance_os.domain.models.methodology import MethodologySpec


@dataclass(frozen=True, slots=True)
class FlowConfig:
    vol_oi_ratio_threshold: float = 2.0
    unusual_vol_threshold: int = 500
    unusual_score_cap: float = 100.0
    unusual_score_per_flag: float = 12.0
    agg_ratio_high: float = 1.5
    agg_ratio_score_mult: float = 10.0
    unusual_dir_threshold: float = 40.0
    flow_bullish_threshold: float = 0.35
    flow_bearish_threshold: float = 0.12


DEFAULT_FLOW_CONFIG = FlowConfig()


def flow_methodology(config: FlowConfig) -> MethodologySpec:
    return MethodologySpec(
        id="options.positioning.flow",
        version="v1",
        model_family="unusual_volume_heuristic",
        assumptions=("High volume vs OI on the same line is flagged as unusual activity.",),
        limitations=("Does not separate opening vs closing; provider volume can be noisy.",),
        references=(),
        parameters={
            "vol_oi_ratio_threshold": str(config.vol_oi_ratio_threshold),
            "unusual_vol_threshold": str(config.unusual_vol_threshold),
        },
    )


def compute_flow_signals(
    calls: list[OptionContract],
    puts: list[OptionContract],
    lit: FinancialLiteracy,
    config: FlowConfig = DEFAULT_FLOW_CONFIG,
) -> list[dict[str, Any]]:
    flagged = 0
    for c in (*calls, *puts):
        oi = max(1, contract_oi(c))
        vol = contract_vol(c)
        ratio = vol / oi
        if ratio > config.vol_oi_ratio_threshold and vol > config.unusual_vol_threshold:
            flagged += 1

    chain_vol = sum(contract_vol(c) for c in calls) + sum(contract_vol(p) for p in puts)
    chain_oi = sum(contract_oi(c) for c in calls) + sum(contract_oi(p) for p in puts)
    agg_ratio = chain_vol / max(1, chain_oi)

    unusual_score = min(
        config.unusual_score_cap,
        float(flagged) * config.unusual_score_per_flag
        + max(0.0, agg_ratio - config.agg_ratio_high) * config.agg_ratio_score_mult,
    )
    unusual_score = round(unusual_score, 4)

    unusual_dir: Literal["bullish", "bearish", "neutral"] = (
        "bullish" if unusual_score >= config.unusual_dir_threshold else "neutral"
    )
    flow_dir: Literal["bullish", "bearish", "neutral"] = (
        "bullish"
        if agg_ratio >= config.flow_bullish_threshold
        else "bearish" if agg_ratio <= config.flow_bearish_threshold else "neutral"
    )

    return [
        {
            "name": _pt.name_unusual_activity(lit),
            "value": unusual_score,
            "direction": unusual_dir,
            "explanation": _pt.expl_unusual_activity(lit, config.unusual_vol_threshold),
        },
        {
            "name": _pt.name_agg_vol_oi(lit),
            "value": round(agg_ratio, 4),
            "direction": flow_dir,
            "explanation": _pt.expl_agg_vol_oi(lit),
        },
    ]
