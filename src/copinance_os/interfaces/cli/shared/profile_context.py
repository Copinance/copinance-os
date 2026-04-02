"""CLI helpers for profile context selection/prompting."""

from __future__ import annotations

from uuid import UUID

import typer
from rich.console import Console

from copinance_os.domain.models.profile import FinancialLiteracy
from copinance_os.interfaces.cli.shared.container_access import get_container
from copinance_os.research.workflows.profile import (
    CreateProfileRequest,
    GetCurrentProfileRequest,
)


async def ensure_profile_with_literacy(profile_id: UUID | None = None) -> UUID | None:
    """Ensure user has a profile with a literacy level for personalized analysis.

    Args:
        profile_id: Optional explicit profile ID. If provided, no prompting occurs.

    Returns:
        A profile ID if available, otherwise None.
    """
    console = Console()
    if profile_id is not None:
        return profile_id

    container = get_container()
    # Check current profile
    current_profile_uc = container.get_current_profile_use_case()
    current_response = await current_profile_uc.execute(GetCurrentProfileRequest())

    if current_response.profile:
        return UUID(str(current_response.profile.id))

    # No profile exists - prompt user
    console.print("\n[bold yellow]No profile found with financial literacy level[/bold yellow]")
    console.print(
        "Setting your financial literacy level helps provide more personalized analysis results."
    )
    console.print("\nFinancial literacy levels:")
    console.print("  • [cyan]beginner[/cyan]: Simple language, concepts explained")
    console.print("  • [cyan]intermediate[/cyan]: Some technical terms with explanations")
    console.print("  • [cyan]advanced[/cyan]: Technical terminology used freely")

    if not typer.confirm(
        "\nWould you like to set your financial literacy level now?", default=True
    ):
        console.print(
            "\n[yellow]Continuing without profile. Analysis will use default settings.[/yellow]"
        )
        return None

    # Prompt for literacy level
    console.print("\nSelect your financial literacy level:")
    console.print("  1. Beginner")
    console.print("  2. Intermediate")
    console.print("  3. Advanced")

    choice = typer.prompt("Enter choice (1-3)", default="2")
    literacy_map = {
        "1": FinancialLiteracy.BEGINNER,
        "2": FinancialLiteracy.INTERMEDIATE,
        "3": FinancialLiteracy.ADVANCED,
    }
    selected_literacy = literacy_map.get(choice, FinancialLiteracy.INTERMEDIATE)

    create_profile_uc = container.create_profile_use_case()
    create_response = await create_profile_uc.execute(
        CreateProfileRequest(financial_literacy=selected_literacy, display_name=None)
    )

    console.print(
        f"\n✓ Profile created with {selected_literacy.value} literacy level",
        style="bold green",
    )
    return UUID(str(create_response.profile.id))
