"""Typed strategy outputs (aligned time series; no raw pandas across layers)."""

from __future__ import annotations

import math

from pydantic import BaseModel, Field, model_validator


class StrategySignal(BaseModel):
    """Target allocation series aligned 1:1 with a price series (oldest bar first).

    For long-only engines, weights are typically in ``[0, 1]``. Callers map this to
    execution-specific semantics (e.g. next-bar return attribution).
    """

    strategy_id: str = Field(..., min_length=1, description="Strategy or rule identifier")
    weights: list[float] = Field(
        ...,
        description="Per-bar target weights, same length as the associated close series",
    )

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def _finite_weights(self) -> StrategySignal:
        for i, w in enumerate(self.weights):
            if math.isnan(w) or math.isinf(w):
                raise ValueError(f"weight at index {i} must be finite")
        return self
