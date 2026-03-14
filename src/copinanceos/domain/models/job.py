"""Job domain models.

Job is the execution context for workflows (not persisted). It describes scope
(instrument or market), instrument/index, timeframe, and workflow type.
Consumers build Job instances and pass them to a JobRunner (or their own
orchestrator); workflow executors receive Job + context from the runner.
"""

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from copinanceos.domain.models.base import Entity
from copinanceos.domain.models.market import MarketType


class RunJobResult(BaseModel):
    """Result of running a single job via a JobRunner."""

    success: bool
    results: dict[str, Any] | None = None
    error_message: str | None = None


class JobTimeframe(StrEnum):
    """Timeframe categories."""

    SHORT_TERM = "short_term"  # Days to weeks
    MID_TERM = "mid_term"  # Weeks to months
    LONG_TERM = "long_term"  # Months to years


class JobStatus(StrEnum):
    """Status of job execution."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobScope(StrEnum):
    """Scope/target of a job."""

    INSTRUMENT = "instrument"
    MARKET = "market"


class Job(Entity):
    """Workflow execution context (scope, symbol/index, timeframe, type). Not persisted."""

    scope: JobScope = Field(
        default=JobScope.INSTRUMENT,
        description="Target scope for the job (instrument or market)",
    )
    market_type: MarketType | None = Field(
        default=MarketType.EQUITY,
        description="Instrument market segment when scope=instrument",
    )
    instrument_symbol: str | None = Field(
        default=None,
        description="Instrument symbol (required when scope=instrument)",
    )
    market_index: str | None = Field(
        default=None,
        description="Market index symbol for market-wide jobs (e.g., SPY). Used when scope=market",
    )
    timeframe: JobTimeframe = Field(..., description="Job timeframe")
    profile_id: UUID | None = Field(None, description="Optional profile ID for context")
    status: JobStatus = Field(default=JobStatus.PENDING, description="Current status")
    workflow_type: str = Field(..., description="Workflow type (stock, macro, or agent)")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Job configuration")
    results: dict[str, Any] = Field(default_factory=dict, description="Latest results")
    error_message: str | None = Field(None, description="Error message if failed")

    @model_validator(mode="after")
    def _validate_scope(self) -> "Job":
        if self.scope == JobScope.INSTRUMENT:
            if not self.instrument_symbol or not self.instrument_symbol.strip():
                raise ValueError("instrument_symbol is required when scope=instrument")
            self.instrument_symbol = self.instrument_symbol.upper().strip()
            self.market_type = self.market_type or MarketType.EQUITY
            self.market_index = None
        else:
            self.instrument_symbol = None
            self.market_type = None
            self.market_index = (self.market_index or "SPY").upper().strip()
        return self
