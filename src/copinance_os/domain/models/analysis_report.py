"""Standard analysis output envelope (convention: summary, metrics, methodology, assumptions, limitations)."""

from typing import Any

from pydantic import BaseModel, Field


class AnalysisReport(BaseModel):
    """Structured report for human and machine consumers (rule 14)."""

    summary: str = Field(..., description="Plain-language summary")
    key_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured key metrics (numbers, nested dicts allowed)",
    )
    methodology: str = Field(default="", description="How the analysis was performed")
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
