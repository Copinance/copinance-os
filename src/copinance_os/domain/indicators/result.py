"""Typed outputs for indicator computations (avoid untyped raw lists at boundaries)."""

from typing import Any

from pydantic import BaseModel, Field


class IndicatorResult(BaseModel):
    """Result of a single indicator run over a price series."""

    name: str = Field(..., description="Indicator identifier (e.g. sma_20, rsi_14)")
    values: list[float | None] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
