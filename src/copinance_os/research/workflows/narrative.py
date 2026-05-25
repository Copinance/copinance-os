"""Market narrative use case: LLM-generated prose summary of current market conditions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog

from copinance_os.domain.literacy import (
    TieredCopy,
    financial_literacy_prompt_value,
    resolve_financial_literacy,
)
from copinance_os.domain.models.analysis import AnalyzeMarketRequest, AnalyzeMode
from copinance_os.domain.models.analysis.narrative import MarketNarrativeRequest, NarrativeResult
from copinance_os.domain.models.entities.profile import FinancialLiteracy
from copinance_os.domain.models.job import JobTimeframe
from copinance_os.domain.ports.analysis_execution import AnalyzeMarketRunner
from copinance_os.research.workflows.base import UseCase

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Deterministic fallback copy (used when LLM is unavailable)
# ---------------------------------------------------------------------------

_TREND_LABEL: dict[str, TieredCopy] = {
    "bull": TieredCopy(
        beginner="markets are trending upward",
        intermediate="the trend regime is bullish",
        advanced="the trend regime is in bull phase",
    ),
    "bear": TieredCopy(
        beginner="markets are trending downward",
        intermediate="the trend regime is bearish",
        advanced="the trend regime is in bear phase",
    ),
    "neutral": TieredCopy(
        beginner="markets are moving sideways without a clear direction",
        intermediate="the trend regime is neutral",
        advanced="the trend regime is neutral / range-bound",
    ),
}

_VOL_LABEL: dict[str, TieredCopy] = {
    "low": TieredCopy(
        beginner="and markets are calm with low volatility",
        intermediate="with low volatility",
        advanced="with realised vol in the low regime",
    ),
    "normal": TieredCopy(
        beginner="and volatility is at a normal level",
        intermediate="with normal volatility",
        advanced="with realised vol in the normal regime",
    ),
    "high": TieredCopy(
        beginner="and markets are experiencing higher-than-usual swings",
        intermediate="with elevated volatility",
        advanced="with realised vol in the high regime",
    ),
}

_CONFIDENCE_LABEL: dict[str, TieredCopy] = {
    "high": TieredCopy(
        beginner="The signal is strong",
        intermediate="Confidence is high",
        advanced="Confidence is high",
    ),
    "medium": TieredCopy(
        beginner="The signal is moderate",
        intermediate="Confidence is moderate",
        advanced="Confidence is medium",
    ),
    "low": TieredCopy(
        beginner="The signal is weak — interpret with caution",
        intermediate="Confidence is low; treat with caution",
        advanced="Confidence is low — regime boundary likely",
    ),
}

_DISCLAIMER = TieredCopy(
    beginner="This is for learning purposes only and is not investment advice.",
    intermediate="For informational purposes only; not investment advice.",
    advanced="Informational only; not investment advice.",
)


def _build_fallback_narrative(
    trend: str,
    vol: str,
    confidence: str,
    lit: FinancialLiteracy,
) -> str:
    trend_copy = _TREND_LABEL.get(trend, _TREND_LABEL["neutral"]).pick(lit)
    vol_copy = _VOL_LABEL.get(vol, _VOL_LABEL["normal"]).pick(lit)
    confidence_copy = _CONFIDENCE_LABEL.get(confidence, _CONFIDENCE_LABEL["medium"]).pick(lit)
    disclaimer = _DISCLAIMER.pick(lit)
    return f"Currently {trend_copy}, {vol_copy}. {confidence_copy}. {disclaimer}"


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_TEMPLATE = """\
You are a financial market analyst writing a brief daily market summary.
Adapt your language and vocabulary strictly to the {literacy_level} investor level:
- beginner: plain English, no jargon, define any term you use, use analogies
- intermediate: standard market vocabulary, brief sector/indicator context
- advanced: full institutional vocabulary, compact second-order effects, no tutorial definitions

Write exactly 2–3 sentences. Do not use bullet points or headers.
End with: "This is for informational purposes only and does not constitute investment advice."
"""

_USER_PROMPT_TEMPLATE = """\
Current market conditions for {market_index}:
- Trend regime: {trend_regime} (confidence: {confidence})
- Volatility regime: {vol_regime}{vix_line}{breadth_line}{macro_line}

Write a {literacy_level}-level market narrative summary.
"""


def _extract_regime_context(results: dict[str, Any]) -> dict[str, str]:
    """Pull the key regime fields out of the serialised MacroRegimeResult dict."""
    trend_regime = "neutral"
    vol_regime = "normal"
    confidence = "medium"
    vix_line = ""
    breadth_line = ""
    macro_line = ""

    detection = results.get("market_regime_detection") or {}
    trend_data = detection.get("detect_market_trend") or {}
    vol_data = detection.get("detect_volatility_regime") or {}

    if trend_data:
        trend_regime = str(trend_data.get("regime") or "neutral")
        confidence = str(trend_data.get("confidence") or "medium")

    if vol_data:
        vol_regime = str(vol_data.get("regime") or "normal")

    indicators = results.get("market_regime_indicators") or {}
    indicators_data = indicators.get("data") or {}

    vix = indicators_data.get("vix") or {}
    if vix.get("available") and vix.get("current_vix") is not None:
        vix_val = round(float(vix["current_vix"]), 1)
        sentiment = vix.get("sentiment") or ""
        vix_line = f"\n- VIX: {vix_val} ({sentiment})" if sentiment else f"\n- VIX: {vix_val}"

    breadth = indicators_data.get("market_breadth") or {}
    if breadth.get("available") and breadth.get("breadth_ratio") is not None:
        pct = round(float(breadth["breadth_ratio"]) * 100, 0)
        breadth_regime = breadth.get("regime") or ""
        breadth_line = (
            f"\n- Market breadth: {pct:.0f}% of sectors above 50-day MA ({breadth_regime})"
        )

    macro = results.get("macro_regime_indicators") or {}
    macro_data = macro.get("data") or {}
    rates = macro_data.get("rates") or {}
    if rates.get("available"):
        interp = rates.get("interpretation") or {}
        slope = interp.get("yield_curve_slope") or interp.get("slope") or ""
        if slope:
            macro_line = f"\n- Yield curve: {slope}"

    return {
        "trend_regime": trend_regime,
        "vol_regime": vol_regime,
        "confidence": confidence,
        "vix_line": vix_line,
        "breadth_line": breadth_line,
        "macro_line": macro_line,
    }


# ---------------------------------------------------------------------------
# Use case
# ---------------------------------------------------------------------------


class GenerateMarketNarrativeUseCase(UseCase[MarketNarrativeRequest, NarrativeResult]):
    """Generate a short LLM prose summary of current market conditions.

    Internally runs the deterministic market analysis to ground the narrative in
    real data, then calls the LLM provider with a literacy-adapted prompt.

    When the LLM is unavailable (no config, provider error) a deterministic
    template-based narrative is returned with ``NarrativeResult.fallback=True``
    so callers degrade gracefully.
    """

    def __init__(
        self,
        analyze_market_runner: AnalyzeMarketRunner,
        llm_provider: Any | None = None,
    ) -> None:
        self._runner = analyze_market_runner
        self._llm_provider = llm_provider

    async def execute(self, request: MarketNarrativeRequest) -> NarrativeResult:
        lit = resolve_financial_literacy(request.financial_literacy)
        market_index = (request.market_index or "SPY").upper().strip()

        # 1. Run deterministic market analysis to ground the narrative in data
        job_result = await self._runner.run(
            AnalyzeMarketRequest(
                market_index=market_index,
                mode=AnalyzeMode.DETERMINISTIC,
                financial_literacy=lit,
                no_cache=request.no_cache,
                # Silence mypy pydantic-plugin false positives — all have defaults
                timeframe=JobTimeframe.MID_TERM,
                question=None,
                lookback_days=252,
                profile_id=None,
                include_prompt_in_results=False,
                stream=False,
                run_id=None,
                include_vix=True,
                include_market_breadth=True,
                include_sector_rotation=False,
                include_rates=True,
                include_credit=False,
                include_commodities=False,
                include_labor=False,
                include_housing=False,
                include_manufacturing=False,
                include_consumer=False,
                include_global=False,
                include_advanced=False,
            )
        )

        results: dict[str, Any] = job_result.results or {}
        ctx = _extract_regime_context(results)
        fallback = False

        # 2. Attempt LLM narrative generation
        narrative: str | None = None
        if self._llm_provider is not None:
            try:
                available = await self._llm_provider.is_available()
                if available:
                    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
                        literacy_level=financial_literacy_prompt_value(lit),
                    )
                    user_prompt = _USER_PROMPT_TEMPLATE.format(
                        market_index=market_index,
                        trend_regime=ctx["trend_regime"],
                        confidence=ctx["confidence"],
                        vol_regime=ctx["vol_regime"],
                        vix_line=ctx["vix_line"],
                        breadth_line=ctx["breadth_line"],
                        macro_line=ctx["macro_line"],
                        literacy_level=financial_literacy_prompt_value(lit),
                    )
                    narrative = await self._llm_provider.generate_text(
                        prompt=user_prompt,
                        system_prompt=system_prompt,
                        temperature=0.3,
                        max_tokens=256,
                    )
                    logger.debug(
                        "Market narrative generated via LLM",
                        market_index=market_index,
                        literacy=lit.value,
                        provider=self._llm_provider.get_provider_name(),
                    )
            except Exception as e:
                logger.warning(
                    "LLM narrative generation failed; using deterministic fallback",
                    market_index=market_index,
                    error=str(e),
                )

        # 3. Deterministic fallback
        if not narrative:
            narrative = _build_fallback_narrative(
                trend=ctx["trend_regime"],
                vol=ctx["vol_regime"],
                confidence=ctx["confidence"],
                lit=lit,
            )
            fallback = True
            logger.info(
                "Market narrative produced from deterministic fallback",
                market_index=market_index,
                literacy=lit.value,
            )

        return NarrativeResult(
            narrative=narrative,
            literacy=lit,
            market_index=market_index,
            generated_at=datetime.now(UTC),
            fallback=fallback,
        )
