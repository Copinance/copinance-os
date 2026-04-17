"""Analysis profile domain model."""

from enum import StrEnum

from pydantic import Field

from copinance_os.domain.models.base import Entity


class FinancialLiteracy(StrEnum):
    """Audience depth for analysis wording (profile + job context).

    Use :func:`copinance_os.domain.literacy.resolve_financial_literacy` when reading optional
    context values, and :class:`copinance_os.domain.literacy.TieredCopy` for deterministic
    multi-tier strings in ``copinance_os.data.literacy`` (one module per feature).
    """

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class AnalysisProfile(Entity):
    """
    Analysis profile entity for contextualizing analysis output.

    AnalysisProfile provides context for how analysis
    should be executed and presented. Integrating applications handle their own
    user management and map users to analysis profiles as needed.
    """

    financial_literacy: FinancialLiteracy = Field(
        default=FinancialLiteracy.INTERMEDIATE,
        description="Financial literacy level for output adaptation",
    )
    preferences: dict[str, str] = Field(
        default_factory=dict, description="Analysis preferences and defaults"
    )
    display_name: str | None = Field(None, description="Optional display name for the profile")
