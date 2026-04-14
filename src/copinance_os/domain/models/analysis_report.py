"""Standard analysis output envelope (summary, metrics, structured methodology)."""

from typing import Any

from pydantic import BaseModel, Field

from copinance_os.domain.models.methodology import AnalysisMethodology


class AnalysisReport(BaseModel):
    """Structured report for human and machine consumers (rule 14)."""

    summary: str = Field(..., description="Plain-language summary")
    key_metrics: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured key metrics (numbers, nested dicts allowed)",
    )
    methodology: AnalysisMethodology = Field(
        ...,
        description="How the analysis was performed (specs + data inputs)",
    )
