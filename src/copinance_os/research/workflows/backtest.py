"""Backtest workflow request models (orchestration runs via ``ResearchOrchestrator``)."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, Field, model_validator


class SimpleLongOnlyWorkflowRequest(BaseModel):
    """Input for ``ResearchOrchestrator.run_simple_long_only_backtest``."""

    closes: list[float] = Field(..., min_length=2)
    weights: list[float] = Field(..., min_length=1)
    strategy_id: str = Field(
        default="workflow",
        min_length=1,
        description="Label for ``StrategySignal`` (auditing / reports)",
    )
    initial_cash: float = Field(default=100_000.0, gt=0)
    commission_bps: float = Field(default=0.0, ge=0)
    slippage_bps: float = Field(default=0.0, ge=0)
    trading_days_per_year: int = Field(default=252, ge=1)

    @model_validator(mode="after")
    def _weights_align_with_closes(self) -> Self:
        if len(self.weights) != len(self.closes):
            raise ValueError("weights must have the same length as closes")
        return self
