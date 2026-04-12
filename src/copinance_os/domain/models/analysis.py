"""Analysis request models and execution routing helpers."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from copinance_os.domain.models.job import JobScope, JobTimeframe
from copinance_os.domain.models.llm_conversation import (
    LLMConversationTurn,
    validate_conversation_history_pairs,
)
from copinance_os.domain.models.market import MarketType, OptionSide

# Executor routing keys (scope + mode)
INSTRUMENT_DETERMINISTIC_TYPE = "deterministic_instrument_analysis"
INSTRUMENT_QUESTION_DRIVEN_TYPE = "question_driven_instrument_analysis"
MARKET_DETERMINISTIC_TYPE = "deterministic_market_analysis"
MARKET_QUESTION_DRIVEN_TYPE = "question_driven_market_analysis"


class AnalyzeMode(StrEnum):
    """Execution mode for analysis (deterministic pipeline vs question-driven)."""

    AUTO = "auto"
    DETERMINISTIC = "deterministic"
    QUESTION_DRIVEN = "question_driven"


def execution_type_from_scope_and_mode(scope: JobScope, mode: AnalyzeMode) -> str:
    """Return the execution type string for the given scope and analysis mode (for Job and executor routing)."""
    if scope == JobScope.INSTRUMENT:
        return (
            INSTRUMENT_QUESTION_DRIVEN_TYPE
            if mode == AnalyzeMode.QUESTION_DRIVEN
            else INSTRUMENT_DETERMINISTIC_TYPE
        )
    return (
        MARKET_QUESTION_DRIVEN_TYPE
        if mode == AnalyzeMode.QUESTION_DRIVEN
        else MARKET_DETERMINISTIC_TYPE
    )


def get_default_instrument_timeframe(market_type: MarketType) -> JobTimeframe:
    """Return the default timeframe for an instrument market type."""
    if market_type == MarketType.OPTIONS:
        return JobTimeframe.SHORT_TERM
    return JobTimeframe.MID_TERM


def resolve_analyze_mode(mode: AnalyzeMode, question: str | None) -> AnalyzeMode:
    """Resolve AUTO into DETERMINISTIC or QUESTION_DRIVEN based on question presence."""
    normalized_question = (question or "").strip()
    if mode == AnalyzeMode.AUTO:
        return AnalyzeMode.QUESTION_DRIVEN if normalized_question else AnalyzeMode.DETERMINISTIC
    return mode


def merge_instrument_expiration_inputs(
    expiration_date: str | None,
    expiration_dates: list[str] | None,
) -> list[str]:
    """Merge single-date and list inputs into deduplicated YYYY-MM-DD strings (order preserved).

    Raises ValueError if any segment is not a valid calendar date in that format.
    """
    ordered: list[str] = []
    seen: set[str] = set()

    def _push(raw: str) -> None:
        s = raw.strip()
        if not s:
            return
        datetime.strptime(s, "%Y-%m-%d")
        if s not in seen:
            seen.add(s)
            ordered.append(s)

    if expiration_dates:
        for d in expiration_dates:
            _push(d)
    if expiration_date:
        _push(expiration_date)
    return ordered


class AnalyzeInstrumentRequest(BaseModel):
    """Request to analyze an instrument statically or agentically."""

    symbol: str = Field(..., description="Instrument symbol")
    market_type: MarketType = Field(
        MarketType.EQUITY,
        description="Instrument market segment",
    )
    timeframe: JobTimeframe | None = Field(
        None,
        description="Analysis timeframe. Defaults by market type when omitted.",
    )
    question: str | None = Field(
        None,
        description="Optional natural-language question. When set, analyze can run agentically.",
    )
    mode: AnalyzeMode = Field(
        AnalyzeMode.AUTO,
        description="Execution mode: auto, deterministic, or question_driven",
    )
    expiration_date: str | None = Field(
        None,
        description="Optional expiration date (YYYY-MM-DD) for options analysis",
    )
    expiration_dates: list[str] | None = Field(
        None,
        description=(
            "Optional list of expiration dates (YYYY-MM-DD) for options analysis. "
            "Merged with expiration_date when both are set (deduplicated)."
        ),
    )
    option_side: OptionSide = Field(
        OptionSide.ALL,
        description="Options side hint when market_type is options",
    )
    profile_id: UUID | None = Field(None, description="Profile ID for context")
    include_prompt_in_results: bool = Field(
        False,
        description="Whether to include rendered prompts in question-driven results",
    )
    stream: bool = Field(
        False,
        description="Stream LLM tokens to stdout during question-driven runs (library/CLI)",
    )
    run_id: str | None = Field(
        None,
        max_length=128,
        description="Optional correlation id for progress streams and structured logs (HTTP/SSE clients)",
    )
    no_cache: bool = Field(
        False,
        description="When True, skip tool/data cache reads and writes for this run",
    )
    positioning_window: Literal["near", "mid"] | None = Field(
        None,
        description="Options positioning horizon (near vs mid); only used when market_type is options",
    )
    conversation_history: list[LLMConversationTurn] = Field(
        default_factory=list,
        description=(
            "Prior user/assistant turns for multi-turn question-driven analysis. "
            "Must be alternating user, assistant, … and end with assistant; "
            "the new user message is `question`."
        ),
    )

    @model_validator(mode="after")
    def _validate_request(self) -> AnalyzeInstrumentRequest:
        if not self.symbol or not self.symbol.strip():
            raise ValueError("symbol is required")

        if self.market_type != MarketType.OPTIONS:
            if self.expiration_date is not None:
                raise ValueError("expiration_date is only supported for options analysis")
            if self.expiration_dates:
                raise ValueError("expiration_dates is only supported for options analysis")
            if self.option_side != OptionSide.ALL:
                raise ValueError("option_side is only supported for options analysis")
        else:
            merge_instrument_expiration_inputs(self.expiration_date, self.expiration_dates)

        if self.market_type != MarketType.OPTIONS and self.positioning_window is not None:
            raise ValueError("positioning_window is only supported for options analysis")

        resolved_mode = resolve_analyze_mode(self.mode, self.question)
        normalized_question = (self.question or "").strip()
        if resolved_mode == AnalyzeMode.QUESTION_DRIVEN and not normalized_question:
            raise ValueError("question is required when mode=question_driven")
        if self.mode == AnalyzeMode.DETERMINISTIC and normalized_question:
            raise ValueError("question cannot be provided when mode=deterministic")
        if self.mode == AnalyzeMode.DETERMINISTIC and self.conversation_history:
            raise ValueError("conversation_history is only supported for question-driven analysis")
        if resolved_mode == AnalyzeMode.QUESTION_DRIVEN:
            validate_conversation_history_pairs(self.conversation_history)

        if self.question is not None:
            self.question = normalized_question or None
        self.symbol = self.symbol.upper().strip()
        return self


class AnalyzeMarketRequest(BaseModel):
    """Request to analyze the broader market statically or agentically."""

    market_index: str = Field("SPY", description="Market index symbol (e.g. SPY, QQQ)")
    timeframe: JobTimeframe = Field(
        JobTimeframe.MID_TERM,
        description="Analysis timeframe context",
    )
    question: str | None = Field(
        None,
        description="Optional natural-language question. When set, analyze can run agentically.",
    )
    mode: AnalyzeMode = Field(
        AnalyzeMode.AUTO,
        description="Execution mode: auto, deterministic, or question_driven",
    )
    lookback_days: int = Field(252, ge=1, le=2520, description="Lookback days (default 252)")
    include_vix: bool = Field(True, description="Include VIX analysis")
    include_market_breadth: bool = Field(True, description="Include market breadth")
    include_sector_rotation: bool = Field(True, description="Include sector rotation")
    include_rates: bool = Field(True, description="Include interest rates")
    include_credit: bool = Field(True, description="Include credit spreads")
    include_commodities: bool = Field(True, description="Include commodities/energy")
    include_labor: bool = Field(True, description="Include labor indicators")
    include_housing: bool = Field(True, description="Include housing indicators")
    include_manufacturing: bool = Field(True, description="Include manufacturing")
    include_consumer: bool = Field(True, description="Include consumer spending/confidence")
    include_global: bool = Field(True, description="Include global indicators")
    include_advanced: bool = Field(True, description="Include advanced indicators")
    profile_id: UUID | None = Field(None, description="Profile ID for context")
    include_prompt_in_results: bool = Field(
        False,
        description="Whether to include rendered prompts in question-driven results",
    )
    stream: bool = Field(
        False,
        description="Stream LLM tokens to stdout during question-driven runs (library/CLI)",
    )
    run_id: str | None = Field(
        None,
        max_length=128,
        description="Optional correlation id for progress streams and structured logs (HTTP/SSE clients)",
    )
    no_cache: bool = Field(
        False,
        description="When True, skip tool/data cache reads and writes for this run",
    )
    conversation_history: list[LLMConversationTurn] = Field(
        default_factory=list,
        description=(
            "Prior user/assistant turns for multi-turn question-driven analysis. "
            "Must be alternating user, assistant, … and end with assistant; "
            "the new user message is `question`."
        ),
    )

    @model_validator(mode="after")
    def _validate_request(self) -> AnalyzeMarketRequest:
        resolved_mode = resolve_analyze_mode(self.mode, self.question)
        normalized_question = (self.question or "").strip()
        if resolved_mode == AnalyzeMode.QUESTION_DRIVEN and not normalized_question:
            raise ValueError("question is required when mode=question_driven")
        if self.mode == AnalyzeMode.DETERMINISTIC and normalized_question:
            raise ValueError("question cannot be provided when mode=deterministic")
        if self.mode == AnalyzeMode.DETERMINISTIC and self.conversation_history:
            raise ValueError("conversation_history is only supported for question-driven analysis")
        if resolved_mode == AnalyzeMode.QUESTION_DRIVEN:
            validate_conversation_history_pairs(self.conversation_history)

        if not self.market_index or not self.market_index.strip():
            raise ValueError("market_index is required")

        if self.question is not None:
            self.question = normalized_question or None
        self.market_index = self.market_index.upper().strip()
        return self
