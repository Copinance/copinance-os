"""Macroeconomic domain models."""

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from copinanceos.domain.models.base import ValueObject


class MacroDataPoint(ValueObject):
    """Value object representing a macroeconomic time-series point."""

    series_id: str = Field(..., description="Provider series identifier (e.g., FRED series id)")
    timestamp: datetime = Field(..., description="Observation timestamp")
    value: Decimal = Field(..., description="Observation value")
    metadata: dict[str, str] = Field(default_factory=dict, description="Additional metadata")
