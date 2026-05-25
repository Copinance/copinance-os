"""Domain models for LLM-curated follow-up question chips (BFF / library consumers)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError

from copinance_os.domain.exceptions import ValidationError
from copinance_os.domain.models.entities.profile import FinancialLiteracy
from copinance_os.domain.models.entities.stock import Stock
from copinance_os.domain.models.market.fundamentals import StockFundamentals
from copinance_os.domain.models.market.types import OptionsChain


class ArtifactType(StrEnum):
    """Payload shape for curated-question generation (not OS use-case names)."""

    OPTIONS_CHAIN = "options_chain"
    QUOTE = "quote"
    HISTORICAL_BARS = "historical_bars"
    INSTRUMENT = "instrument"
    FUNDAMENTALS = "fundamentals"
    MARKET_REGIME = "market_regime"
    MACRO_SNAPSHOT = "macro_snapshot"
    SECTOR_ROTATION = "sector_rotation"
    UPCOMING_EVENTS = "upcoming_events"
    WATCHLIST_RISK = "watchlist_risk"
    OPTIONS_POSITIONING = "options_positioning"


class LLMUnavailableReason(StrEnum):
    """Typed reason when curated questions could not be LLM-generated."""

    NO_LLM_CONFIG = "no_llm_config"
    PROVIDER_ERROR = "provider_error"
    PARSE_ERROR = "parse_error"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"


class CuratedQuestion(BaseModel):
    """A suggested follow-up question for question-driven analyze."""

    text: str = Field(..., min_length=1, max_length=500)
    focus: str | None = Field(None, max_length=120)
    suggested_tools: list[str] | None = Field(
        None,
        description="Soft hint: tool registry names for orchestrator pre-selection",
    )
    requires_symbol: str | None = Field(
        None,
        max_length=32,
        description="Symbol to attach when artifact is multi-symbol (watchlist, sectors)",
    )


class CuratedQuestionsMeta(BaseModel):
    """Metadata for a curated-questions block."""

    artifact: ArtifactType
    requested_count: int
    llm_enabled: bool
    llm_unavailable_reason: LLMUnavailableReason | None = None
    generated_at: datetime | None = None
    cache_hit: bool = False
    numeric_grounding_policy: str


class CuratedQuestionsBlock(BaseModel):
    """Result of curated-question generation."""

    questions: list[CuratedQuestion] = Field(default_factory=list)
    meta: CuratedQuestionsMeta


class GenerateCuratedQuestionsRequest(BaseModel):
    """Request to generate curated follow-up questions from an already-fetched payload."""

    artifact: ArtifactType
    payload: dict[str, Any] = Field(
        ...,
        description="Already-fetched data (validated per artifact before LLM call)",
    )
    count: int = Field(3, ge=1, le=10)
    financial_literacy: FinancialLiteracy | None = None
    learning_step: int | None = Field(
        None,
        ge=1,
        le=8,
        description="Optional dashboard learning-step index for tier-1 consumers",
    )
    no_cache: bool = False


# ---------------------------------------------------------------------------
# Per-artifact payload schemas (minimum shape; extra fields allowed)
# ---------------------------------------------------------------------------


class QuotePayload(BaseModel):
    """Quote dict from get_quote (symbol required)."""

    model_config = {"extra": "allow"}

    symbol: str


class HistoricalBarsPayload(BaseModel):
    """Historical OHLCV payload: bars under ``data`` or ``bars``."""

    model_config = {"extra": "allow"}

    symbol: str | None = None
    data: list[dict[str, Any]] | None = None
    bars: list[dict[str, Any]] | None = None
    interval: str | None = None


class MarketRegimePayload(BaseModel):
    """Market regime / market_context style dict."""

    model_config = {"extra": "allow"}

    market_index: str | None = None
    trend_regime: str | None = None
    vol_regime: str | None = None
    confidence: str | float | None = None


class MacroSnapshotPayload(BaseModel):
    """Macro indicator table snapshot."""

    model_config = {"extra": "allow"}

    indicators: list[dict[str, Any]] = Field(default_factory=list)


class SectorRotationPayload(BaseModel):
    """Sector momentum / rotation table."""

    model_config = {"extra": "allow"}

    sectors: list[dict[str, Any]] = Field(default_factory=list)


class UpcomingEventsPayload(BaseModel):
    """Upcoming events calendar."""

    model_config = {"extra": "allow"}

    events: list[dict[str, Any]] = Field(default_factory=list)


class WatchlistRiskPayload(BaseModel):
    """Multi-symbol watchlist risk summary."""

    model_config = {"extra": "allow"}

    items: list[dict[str, Any]] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)


class OptionsPositioningPayload(BaseModel):
    """Options positioning aggregate (GEX / OI / bias)."""

    model_config = {"extra": "allow"}

    symbol: str
    window: str | None = None
    market_bias: str | None = None
    confidence: float | None = None


def _validation_error(field: str, message: str) -> ValidationError:
    return ValidationError(field=field, message=message)


def validate_artifact_payload(artifact: ArtifactType, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate ``payload`` for ``artifact``; return normalized dict for context builders.

    Raises:
        ValidationError: When payload does not match the artifact schema.
    """
    try:
        match artifact:
            case ArtifactType.OPTIONS_CHAIN:
                return OptionsChain.model_validate(payload).model_dump(mode="json")
            case ArtifactType.QUOTE:
                return QuotePayload.model_validate(payload).model_dump(mode="json")
            case ArtifactType.HISTORICAL_BARS:
                dumped = HistoricalBarsPayload.model_validate(payload).model_dump(mode="json")
                bars = dumped.get("data") or dumped.get("bars") or []
                if not bars:
                    raise _validation_error(
                        "payload",
                        "historical_bars requires non-empty 'data' or 'bars' list",
                    )
                return dumped
            case ArtifactType.INSTRUMENT:
                return Stock.model_validate(payload).model_dump(mode="json")
            case ArtifactType.FUNDAMENTALS:
                return StockFundamentals.model_validate(payload).model_dump(mode="json")
            case ArtifactType.MARKET_REGIME:
                return MarketRegimePayload.model_validate(payload).model_dump(mode="json")
            case ArtifactType.MACRO_SNAPSHOT:
                return MacroSnapshotPayload.model_validate(payload).model_dump(mode="json")
            case ArtifactType.SECTOR_ROTATION:
                sector = SectorRotationPayload.model_validate(payload)
                if not sector.sectors:
                    raise _validation_error("sectors", "sector_rotation requires non-empty sectors")
                return sector.model_dump(mode="json")
            case ArtifactType.UPCOMING_EVENTS:
                events = UpcomingEventsPayload.model_validate(payload)
                if not events.events:
                    raise _validation_error("events", "upcoming_events requires non-empty events")
                return events.model_dump(mode="json")
            case ArtifactType.WATCHLIST_RISK:
                watchlist = WatchlistRiskPayload.model_validate(payload)
                if not watchlist.items and not watchlist.symbols:
                    raise _validation_error(
                        "payload",
                        "watchlist_risk requires non-empty items or symbols",
                    )
                return watchlist.model_dump(mode="json")
            case ArtifactType.OPTIONS_POSITIONING:
                return OptionsPositioningPayload.model_validate(payload).model_dump(mode="json")
    except PydanticValidationError as exc:
        raise _validation_error("payload", str(exc)) from exc
    raise _validation_error("artifact", f"unsupported artifact: {artifact}")


def curated_questions_cache_key_kwargs(
    *,
    artifact: ArtifactType,
    payload: dict[str, Any],
    literacy_value: str,
    count: int,
    learning_step: int | None,
) -> dict[str, Any]:
    """Kwargs for :meth:`CacheManager.get` / ``set`` curated_questions namespace."""
    canonical = json.dumps(payload, sort_keys=True, default=str)
    payload_hash = hashlib.sha256(canonical.encode()).hexdigest()
    return {
        "artifact": artifact.value,
        "payload_hash": payload_hash,
        "literacy": literacy_value,
        "count": count,
        "learning_step": learning_step if learning_step is not None else "",
    }


def utc_now() -> datetime:
    return datetime.now(UTC)


def filter_suggested_tools(
    names: list[str] | None,
    allowed: frozenset[str],
) -> list[str] | None:
    """Drop unknown tool names; return None if input was None."""
    if names is None:
        return None
    filtered = [n for n in names if n in allowed]
    return filtered or None
