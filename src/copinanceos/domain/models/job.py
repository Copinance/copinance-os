"""Job domain models.

Job is the execution context for workflows (not persisted). It describes scope
(stock or market), symbol/index, timeframe, and workflow type. Used by
RunWorkflowUseCase and workflow executors only.
"""

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field, model_validator

from copinanceos.domain.models.base import Entity


class JobTimeframe(str, Enum):
    """Timeframe categories."""

    SHORT_TERM = "short_term"  # Days to weeks
    MID_TERM = "mid_term"  # Weeks to months
    LONG_TERM = "long_term"  # Months to years


class JobStatus(str, Enum):
    """Status of job execution."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobScope(str, Enum):
    """Scope/target of a job."""

    STOCK = "stock"
    MARKET = "market"


class Job(Entity):
    """Workflow execution context (scope, symbol/index, timeframe, type). Not persisted."""

    scope: JobScope = Field(
        default=JobScope.STOCK,
        description="Target scope for the job (stock or market)",
    )
    stock_symbol: str | None = Field(
        default=None, description="Stock symbol (required when scope=stock)"
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
        if self.scope == JobScope.STOCK:
            if not self.stock_symbol or not self.stock_symbol.strip():
                raise ValueError("stock_symbol is required when scope=stock")
            self.stock_symbol = self.stock_symbol.upper().strip()
            self.market_index = None
        else:
            self.stock_symbol = None
            self.market_index = (self.market_index or "SPY").upper().strip()
        return self
