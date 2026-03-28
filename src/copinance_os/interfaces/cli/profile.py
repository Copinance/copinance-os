"""Profile-related CLI commands."""

import asyncio
from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table

from copinance_os.domain.models.profile import FinancialLiteracy
from copinance_os.infra.di import container
from copinance_os.research.workflows.profile import (
    CreateProfileRequest,
    DeleteProfileRequest,
    GetCurrentProfileRequest,
    GetProfileRequest,
    ListProfilesRequest,
    SetCurrentProfileRequest,
)

profile_app = typer.Typer(help="Analysis profile management commands")
console = Console()


@profile_app.command("create")
def create_profile(
    literacy: FinancialLiteracy = typer.Option(
        FinancialLiteracy.BEGINNER, help="Financial literacy level"
    ),
    name: str | None = typer.Option(None, help="Display name for the profile"),
) -> None:
    """Create a new analysis profile."""

    async def _create() -> None:
        use_case = container.create_profile_use_case()
        request = CreateProfileRequest(
            financial_literacy=literacy,
            display_name=name,
            preferences={},
        )
        response = await use_case.execute(request)

        console.print("✓ Profile created successfully", style="bold green")
        console.print(f"ID: {response.profile.id}")
        console.print(f"Financial Literacy: {response.profile.financial_literacy.value}")
        if response.profile.display_name:
            console.print(f"Display Name: {response.profile.display_name}")
        console.print("✓ Set as current profile", style="bold cyan")

    asyncio.run(_create())


@profile_app.command("list")
def list_profiles(
    limit: int = typer.Option(100, help="Maximum number of profiles to show"),
) -> None:
    """List all analysis profiles."""

    async def _list() -> None:
        use_case = container.list_profiles_use_case()
        request = ListProfilesRequest(limit=limit)
        response = await use_case.execute(request)

        if not response.profiles:
            console.print("No profiles found", style="yellow")
            return

        # Get current profile ID
        current_use_case = container.get_current_profile_use_case()
        current_response = await current_use_case.execute(GetCurrentProfileRequest())
        current_id = current_response.profile.id if current_response.profile else None

        table = Table(title="Analysis Profiles")
        table.add_column("ID", style="cyan")
        table.add_column("Display Name", style="magenta")
        table.add_column("Financial Literacy", style="green")
        table.add_column("Preferences", style="yellow")
        table.add_column("Current", style="bright_cyan")

        for profile in response.profiles:
            prefs_str = ", ".join(f"{k}={v}" for k, v in profile.preferences.items()) or "None"
            is_current = "✓" if profile.id == current_id else ""
            table.add_row(
                str(profile.id),
                profile.display_name or "N/A",
                profile.financial_literacy.value,
                prefs_str,
                is_current,
            )

        console.print(table)

    asyncio.run(_list())


@profile_app.command("get")
def get_profile(
    profile_id: UUID = typer.Argument(..., help="Profile ID"),
) -> None:
    """Get profile details."""

    async def _get() -> None:
        use_case = container.get_profile_use_case()
        request = GetProfileRequest(profile_id=profile_id)
        response = await use_case.execute(request)

        if response.profile is None:
            console.print("Profile not found", style="bold red")
            return

        profile = response.profile
        console.print("\n[bold]Profile Details[/bold]")
        console.print(f"ID: {profile.id}")
        console.print(f"Financial Literacy: {profile.financial_literacy.value}")
        if profile.display_name:
            console.print(f"Display Name: {profile.display_name}")
        if profile.preferences:
            console.print("\n[bold]Preferences:[/bold]")
            for key, value in profile.preferences.items():
                console.print(f"  {key}: {value}")

    asyncio.run(_get())


@profile_app.command("current")
def get_current_profile() -> None:
    """Get the current profile."""

    async def _get_current() -> None:
        use_case = container.get_current_profile_use_case()
        request = GetCurrentProfileRequest()
        response = await use_case.execute(request)

        if response.profile is None:
            console.print("No current profile set", style="yellow")
            console.print("Create a profile or set one with: profile set-current <profile-id>")
            return

        profile = response.profile
        console.print("\n[bold]Current Profile[/bold]")
        console.print(f"ID: {profile.id}")
        console.print(f"Financial Literacy: {profile.financial_literacy.value}")
        if profile.display_name:
            console.print(f"Display Name: {profile.display_name}")
        if profile.preferences:
            console.print("\n[bold]Preferences:[/bold]")
            for key, value in profile.preferences.items():
                console.print(f"  {key}: {value}")

    asyncio.run(_get_current())


@profile_app.command("set-current")
def set_current_profile(
    profile_id: UUID | None = typer.Argument(
        None, help="Profile ID to set as current (omit to clear)"
    ),
) -> None:
    """Set or clear the current profile."""

    async def _set_current() -> None:
        use_case = container.set_current_profile_use_case()
        request = SetCurrentProfileRequest(profile_id=profile_id)

        try:
            response = await use_case.execute(request)
            if response.profile:
                console.print("✓ Current profile set", style="bold green")
                console.print(f"ID: {response.profile.id}")
                if response.profile.display_name:
                    console.print(f"Display Name: {response.profile.display_name}")
            else:
                console.print("✓ Current profile cleared", style="bold green")
        except ValueError as e:
            console.print(f"✗ Error: {e}", style="bold red")

    asyncio.run(_set_current())


@profile_app.command("delete")
def delete_profile(
    profile_id: UUID = typer.Argument(..., help="Profile ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without confirmation"),
) -> None:
    """Delete an analysis profile."""

    async def _delete() -> None:
        # Get profile first to show details
        get_use_case = container.get_profile_use_case()
        get_request = GetProfileRequest(profile_id=profile_id)
        get_response = await get_use_case.execute(get_request)

        if get_response.profile is None:
            console.print("Profile not found", style="bold red")
            return

        profile = get_response.profile

        # Check if it's the current profile
        current_use_case = container.get_current_profile_use_case()
        current_response = await current_use_case.execute(GetCurrentProfileRequest())
        is_current = (
            current_response.profile is not None and current_response.profile.id == profile_id
        )

        # Confirm deletion unless forced
        if not force:
            console.print("\n[bold]Profile to delete:[/bold]")
            console.print(f"ID: {profile.id}")
            if profile.display_name:
                console.print(f"Display Name: {profile.display_name}")
            console.print(f"Financial Literacy: {profile.financial_literacy.value}")
            if is_current:
                console.print("[yellow]⚠ This is the current profile[/yellow]")

            confirm = typer.confirm("\nAre you sure you want to delete this profile?")
            if not confirm:
                console.print("Deletion cancelled", style="yellow")
                return

        # Delete the profile
        use_case = container.delete_profile_use_case()
        request = DeleteProfileRequest(profile_id=profile_id)

        try:
            response = await use_case.execute(request)
            if response.success:
                console.print("✓ Profile deleted successfully", style="bold green")
                if is_current:
                    console.print("Current profile cleared", style="dim")
            else:
                console.print("✗ Failed to delete profile", style="bold red")
        except ValueError as e:
            console.print(f"✗ Error: {e}", style="bold red")

    asyncio.run(_delete())
