"""Pydantic contracts for minimal backtests (no raw pandas across modules)."""

from typing import Any

from pydantic import BaseModel, Field


class SimpleBacktestConfig(BaseModel):
    """Long-only allocation backtest with explicit friction."""

    initial_cash: float = Field(gt=0, description="Starting portfolio currency units")
    commission_bps: float = Field(
        ge=0,
        default=0.0,
        description="Round-trip commission in basis points applied on turnover notional",
    )
    slippage_bps: float = Field(
        ge=0,
        default=0.0,
        description="Additional implementation shortfall in bps on turnover notional",
    )
    trading_days_per_year: int = Field(default=252, ge=1)


class SimpleBacktestResult(BaseModel):
    """Structured backtest output (summary + metrics + methodology text)."""

    equity_curve: list[float] = Field(description="Portfolio value at each close")
    period_returns: list[float | None] = Field(
        description="Per-period strategy return after costs; None for index 0",
    )
    total_return: float
    max_drawdown: float
    sharpe_ratio: float | None = Field(
        None,
        description="Annualized Sharpe on period returns when sample is sufficient",
    )
    methodology: str
    assumptions: list[str]
    limitations: list[str]
    key_metrics: dict[str, Any] = Field(default_factory=dict)
