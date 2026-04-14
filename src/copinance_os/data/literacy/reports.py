"""Tiered report-level assumptions and limitations."""

from __future__ import annotations

from copinance_os.domain.literacy import TieredCopy
from copinance_os.domain.models.profile import FinancialLiteracy


def report_assumptions(lit: FinancialLiteracy) -> tuple[str, str]:
    return (
        TieredCopy(
            beginner="Some market data can arrive late or have gaps depending on the source.",
            intermediate="Market data may be delayed or incomplete; provider-dependent.",
            advanced="Market data may be delayed/incomplete by provider.",
        ).pick(lit),
        TieredCopy(
            beginner="Financial ratios use the latest company reports loaded in this run.",
            intermediate="Ratios use latest reported fundamentals within the pipeline window.",
            advanced="Ratios use latest reported fundamentals in-window.",
        ).pick(lit),
    )


def report_limitations(lit: FinancialLiteracy) -> tuple[str, str]:
    return (
        TieredCopy(
            beginner="This is research information, not a buy or sell instruction.",
            intermediate="Not investment advice; for research and education only.",
            advanced="Not investment advice; research/education only.",
        ).pick(lit),
        TieredCopy(
            beginner="Results do not include trading fees, taxes, or hard-to-trade conditions.",
            intermediate="Does not model transaction costs, taxes, or liquidity.",
            advanced="Excludes transaction costs, taxes, and liquidity constraints.",
        ).pick(lit),
    )
