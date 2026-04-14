"""Tiered narrative helpers for market-regime deterministic outputs."""

from __future__ import annotations

from copinance_os.domain.literacy import TieredCopy
from copinance_os.domain.models.profile import FinancialLiteracy

_VIX_SENTIMENT = {
    "complacent": TieredCopy(
        beginner="very calm",
        intermediate="complacent",
        advanced="complacent",
    ),
    "normal": TieredCopy(
        beginner="normal",
        intermediate="normal",
        advanced="normal",
    ),
    "fearful": TieredCopy(
        beginner="stressed",
        intermediate="fearful",
        advanced="fearful",
    ),
    "panic": TieredCopy(
        beginner="panic-like",
        intermediate="panic",
        advanced="panic",
    ),
}

_PHASE_DESCRIPTIONS = {
    "markup_strong": TieredCopy(
        beginner="Strong uptrend with heavy trading activity.",
        intermediate="Strong uptrend with high volume - bullish phase",
        advanced="Markup phase with strong trend and elevated volume.",
    ),
    "markup_moderate": TieredCopy(
        beginner="Uptrend with steady trading activity.",
        intermediate="Uptrend with moderate volume - bullish phase",
        advanced="Markup phase with moderate participation.",
    ),
    "markdown_strong": TieredCopy(
        beginner="Strong downtrend with heavy trading activity.",
        intermediate="Strong downtrend with high volume - bearish phase",
        advanced="Markdown phase with strong downside trend and elevated volume.",
    ),
    "markdown_moderate": TieredCopy(
        beginner="Downtrend with steady trading activity.",
        intermediate="Downtrend with moderate volume - bearish phase",
        advanced="Markdown phase with moderate downside participation.",
    ),
    "distribution": TieredCopy(
        beginner="Price is near highs with heavier activity, which can signal a top.",
        intermediate="Price near highs with elevated volume - potential top",
        advanced="Distribution-style setup near highs with elevated volume.",
    ),
    "accumulation": TieredCopy(
        beginner="Price is near lows with lighter activity, which can signal a bottom.",
        intermediate="Price near lows with low volume - potential bottom",
        advanced="Accumulation-style setup near lows with muted volume.",
    ),
    "transition": TieredCopy(
        beginner="Mixed signals and no clear direction.",
        intermediate="Transition phase - unclear direction",
        advanced="Transition regime with mixed directional signals.",
    ),
    "insufficient": TieredCopy(
        beginner="Not enough data to classify the cycle.",
        intermediate="Insufficient data for cycle detection",
        advanced="Insufficient data for cycle regime classification.",
    ),
}

_TREND_REGIME = {
    "bull": TieredCopy("uptrend", "bull", "bull"),
    "bear": TieredCopy("downtrend", "bear", "bear"),
    "neutral": TieredCopy("sideways", "neutral", "neutral"),
}

_VOL_REGIME = {
    "high": TieredCopy("high volatility", "high", "high"),
    "normal": TieredCopy("normal volatility", "normal", "normal"),
    "low": TieredCopy("low volatility", "low", "low"),
}


def vix_sentiment_label(sentiment: str, lit: FinancialLiteracy) -> str:
    tc = _VIX_SENTIMENT.get(sentiment)
    return tc.pick(lit) if tc else sentiment


def cycle_phase_description(key: str, lit: FinancialLiteracy) -> str:
    tc = _PHASE_DESCRIPTIONS.get(key)
    if tc is None:
        return _PHASE_DESCRIPTIONS["transition"].pick(lit)
    return tc.pick(lit)


def trend_regime_label(regime: str, lit: FinancialLiteracy) -> str:
    tc = _TREND_REGIME.get(regime)
    return tc.pick(lit) if tc else regime


def volatility_regime_label(regime: str, lit: FinancialLiteracy) -> str:
    tc = _VOL_REGIME.get(regime)
    return tc.pick(lit) if tc else regime
