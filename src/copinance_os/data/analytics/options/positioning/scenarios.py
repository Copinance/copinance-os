"""Scenario rows (labels + tiered narrative copy)."""

from __future__ import annotations

from typing import Any

from copinance_os.data.literacy import options_positioning as _pt
from copinance_os.domain.literacy import FinancialLiteracy


def build_scenarios(
    symbol: str,
    lit: FinancialLiteracy,
    bullish_probability: float,
    bearish_probability: float,
    neutral_probability: float,
) -> list[dict[str, Any]]:
    scen_bull, scen_bear, scen_range = _pt.scenario_narratives(symbol, lit)
    return [
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
    ]
