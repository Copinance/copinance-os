"""Tiered mappings for deterministic macro interpretation labels."""

from __future__ import annotations

from copinance_os.domain.literacy import TieredCopy
from copinance_os.domain.models.profile import FinancialLiteracy

_LABELS: dict[str, TieredCopy] = {
    "cooling": TieredCopy("cooling", "cooling", "cooling"),
    "heating": TieredCopy("heating up", "heating", "heating"),
    "flat": TieredCopy("flat", "flat", "flat"),
    "very_tight": TieredCopy("very tight", "very_tight", "very_tight"),
    "tight": TieredCopy("tight", "tight", "tight"),
    "normal": TieredCopy("normal", "normal", "normal"),
    "loose": TieredCopy("loose", "loose", "loose"),
    "strong_growth": TieredCopy("strong growth", "strong_growth", "strong_growth"),
    "moderate_growth": TieredCopy("moderate growth", "moderate_growth", "moderate_growth"),
    "weak_growth": TieredCopy("weak growth", "weak_growth", "weak_growth"),
    "declining": TieredCopy("declining", "declining", "declining"),
    "strong_appreciation": TieredCopy(
        "strong home-price gains", "strong_appreciation", "strong_appreciation"
    ),
    "moderate_appreciation": TieredCopy(
        "moderate home-price gains", "moderate_appreciation", "moderate_appreciation"
    ),
    "strong": TieredCopy("strong", "strong", "strong"),
    "moderate": TieredCopy("moderate", "moderate", "moderate"),
    "weak": TieredCopy("weak", "weak", "weak"),
    "near_full": TieredCopy("near full use", "near_full", "near_full"),
    "underutilized": TieredCopy("underused", "underutilized", "underutilized"),
    "optimistic": TieredCopy("optimistic", "optimistic", "optimistic"),
    "pessimistic": TieredCopy("pessimistic", "pessimistic", "pessimistic"),
    "improving": TieredCopy("improving", "improving", "improving"),
    "deteriorating": TieredCopy("deteriorating", "deteriorating", "deteriorating"),
    "usd_weakening": TieredCopy("dollar weakening", "usd_weakening", "usd_weakening"),
    "usd_steady": TieredCopy("dollar steady", "usd_steady", "usd_steady"),
    "usd_strengthening": TieredCopy(
        "dollar strengthening", "usd_strengthening", "usd_strengthening"
    ),
    "inverted_recession_warning": TieredCopy(
        "yield curve inversion warning", "inverted_recession_warning", "inverted_recession_warning"
    ),
    "inverted_mild_warning": TieredCopy(
        "mild inversion warning", "inverted_mild_warning", "inverted_mild_warning"
    ),
    "flattening": TieredCopy("flattening curve", "flattening", "flattening"),
    "widening_or_flat": TieredCopy("widening or flat", "widening_or_flat", "widening_or_flat"),
    "tightening": TieredCopy("tightening", "tightening", "tightening"),
    "hy_cheap_vs_ig": TieredCopy("high-yield looks cheap", "hy_cheap_vs_ig", "hy_cheap_vs_ig"),
    "hy_expensive_vs_ig": TieredCopy(
        "high-yield looks expensive", "hy_expensive_vs_ig", "hy_expensive_vs_ig"
    ),
    "normal_valuation": TieredCopy("normal valuation", "normal_valuation", "normal_valuation"),
    "elevated": TieredCopy("elevated", "elevated", "elevated"),
    "muted": TieredCopy("muted", "muted", "muted"),
    "risk_on_confirmation": TieredCopy(
        "supports risk-on", "risk_on_confirmation", "risk_on_confirmation"
    ),
}


def interpret_label(value: str, lit: FinancialLiteracy) -> str:
    mapping = _LABELS.get(value)
    if mapping is None:
        return value
    return mapping.pick(lit)
