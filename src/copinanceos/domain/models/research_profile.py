"""Research profile domain model."""

from enum import StrEnum

from pydantic import Field

from copinanceos.domain.models.base import Entity


class FinancialLiteracy(StrEnum):
    """Financial literacy levels for research output adaptation."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ResearchProfile(Entity):
    """
    Research profile entity for contextualizing research output.

    ResearchProfile provides context for how research
    should be executed and presented. Integrating applications handle their own
    user management and map users to research profiles as needed.
    """

    financial_literacy: FinancialLiteracy = Field(
        default=FinancialLiteracy.BEGINNER,
        description="Financial literacy level for output adaptation",
    )
    preferences: dict[str, str] = Field(
        default_factory=dict, description="Research preferences and defaults"
    )
    display_name: str | None = Field(None, description="Optional display name for the profile")
