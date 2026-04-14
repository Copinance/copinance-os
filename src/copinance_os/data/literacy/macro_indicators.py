"""Tiered mappings for deterministic macro interpretation labels."""

from __future__ import annotations

from copinance_os.domain.literacy import TieredCopy
from copinance_os.domain.models.profile import FinancialLiteracy

_LABELS: dict[str, TieredCopy] = {
    "cooling": TieredCopy("cooling down", "cooling", "cooling"),
    "heating": TieredCopy("heating up", "heating", "heating"),
    "flat": TieredCopy("flat", "flat", "flat trend"),
    "very_tight": TieredCopy("very tight", "very_tight", "very tight labor"),
    "tight": TieredCopy("tight", "tight", "tight labor"),
    "normal": TieredCopy("normal", "normal", "baseline"),
    "loose": TieredCopy("loose", "loose", "loose conditions"),
    "strong_growth": TieredCopy("strong growth", "strong_growth", "strong growth"),
    "moderate_growth": TieredCopy("moderate growth", "moderate_growth", "moderate growth"),
    "weak_growth": TieredCopy("weak growth", "weak_growth", "weak growth"),
    "declining": TieredCopy("declining", "declining", "declining trend"),
    "strong_appreciation": TieredCopy(
        "strong home-price gains", "strong_appreciation", "strong_appreciation"
    ),
    "moderate_appreciation": TieredCopy(
        "moderate home-price gains", "moderate_appreciation", "moderate_appreciation"
    ),
    "strong": TieredCopy("strong", "strong", "strong reading"),
    "moderate": TieredCopy("moderate", "moderate", "moderate reading"),
    "weak": TieredCopy("weak", "weak", "weak reading"),
    "near_full": TieredCopy("near full use", "near_full", "near full utilization"),
    "underutilized": TieredCopy("underused", "underutilized", "underutilized"),
    "optimistic": TieredCopy("optimistic", "optimistic", "optimistic stance"),
    "pessimistic": TieredCopy("pessimistic", "pessimistic", "pessimistic stance"),
    "improving": TieredCopy("improving", "improving", "improving trend"),
    "deteriorating": TieredCopy("deteriorating", "deteriorating", "deteriorating trend"),
    "usd_weakening": TieredCopy("dollar weakening", "usd_weakening", "USD weakening"),
    "usd_steady": TieredCopy("dollar steady", "usd_steady", "USD steady"),
    "usd_strengthening": TieredCopy(
        "dollar strengthening", "usd_strengthening", "usd_strengthening"
    ),
    "inverted_recession_warning": TieredCopy(
        "yield curve inversion warning", "inverted_recession_warning", "inverted_recession_warning"
    ),
    "inverted_mild_warning": TieredCopy(
        "mild inversion warning", "inverted_mild_warning", "inverted_mild_warning"
    ),
    "flattening": TieredCopy("flattening curve", "flattening", "curve flattening"),
    "widening_or_flat": TieredCopy("widening or flat", "widening_or_flat", "widening/flat"),
    "tightening": TieredCopy("tightening", "tightening", "tightening trend"),
    "hy_cheap_vs_ig": TieredCopy("high-yield looks cheap", "hy_cheap_vs_ig", "hy_cheap_vs_ig"),
    "hy_expensive_vs_ig": TieredCopy(
        "high-yield looks expensive", "hy_expensive_vs_ig", "hy_expensive_vs_ig"
    ),
    "normal_valuation": TieredCopy("normal valuation", "normal_valuation", "normal valuation"),
    "elevated": TieredCopy("elevated", "elevated", "elevated risk"),
    "muted": TieredCopy("muted", "muted", "muted impulse"),
    "risk_on_confirmation": TieredCopy(
        "supports risk-on", "risk_on_confirmation", "risk_on_confirmation"
    ),
}


def interpret_label(value: str, lit: FinancialLiteracy) -> str:
    mapping = _LABELS.get(value)
    if mapping is None:
        return value
    return mapping.pick(lit)
