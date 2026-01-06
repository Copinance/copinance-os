"""Research domain models."""

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field

from copinanceos.domain.models.base import Entity


class ResearchTimeframe(str, Enum):
    """Research timeframe categories."""

    SHORT_TERM = "short_term"  # Days to weeks
    MID_TERM = "mid_term"  # Weeks to months
    LONG_TERM = "long_term"  # Months to years


class ResearchStatus(str, Enum):
    """Status of research execution."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Research(Entity):
    """Research entity representing a stock research task."""

    stock_symbol: str = Field(..., description="Stock symbol to research")
    timeframe: ResearchTimeframe = Field(..., description="Research timeframe")
    profile_id: UUID | None = Field(None, description="Optional research profile ID for context")
    status: ResearchStatus = Field(
        default=ResearchStatus.PENDING, description="Current research status"
    )
    workflow_type: str = Field(..., description="Type of workflow (stock, macro, or agent)")
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Research parameters and configuration"
    )
    results: dict[str, Any] = Field(
        default_factory=dict, description="Research results and findings"
    )
    error_message: str | None = Field(None, description="Error message if failed")
