"""Time-ordered price series for data-layer contracts (ingestion and indicators)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PriceSeries(BaseModel):
    """Closing prices in chronological order (oldest first).

    Callers are responsible for session boundaries, timezone alignment, and
    corporate actions; this model only carries the numeric series for pipelines.
    When ``timestamps`` is set, it must align one-to-one with ``closes`` (same
    ordering constraint: oldest bar first).
    """

    model_config = ConfigDict(frozen=True)

    closes: list[float] = Field(
        min_length=1,
        description="Closing prices, oldest first",
    )
    timestamps: list[datetime] | None = Field(
        default=None,
        description="Observation times aligned with closes (same length), oldest first",
    )

    @model_validator(mode="after")
    def _timestamps_align_with_closes(self) -> PriceSeries:
        if self.timestamps is not None and len(self.timestamps) != len(self.closes):
            raise ValueError("timestamps must have the same length as closes when provided")
        return self
