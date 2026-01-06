"""CLI error handling utilities.

This module provides utilities for handling errors in the CLI layer,
displaying user-friendly messages and handling different error types appropriately.
"""

from typing import Any

from rich.console import Console
from rich.panel import Panel

from copinanceos.application.exceptions import ApplicationError
from copinanceos.domain.exceptions import DomainError

console = Console()


def handle_cli_error(error: Exception, context: dict[str, Any] | None = None) -> None:
    """Handle errors in CLI commands and display user-friendly messages.

    This function follows the error handling strategy where the CLI layer catches
    all errors and displays user-friendly messages to the user.

    Args:
        error: The exception to handle
        context: Optional context information for error messages

    Examples:
        >>> try:
        ...     result = use_case.execute(request)
        ... except Exception as e:
        ...     handle_cli_error(e)
        ...     return
    """
    context = context or {}

    # Handle domain exceptions (business logic errors)
    if isinstance(error, DomainError):
        _handle_domain_error(error, context)
        return

    # Handle application exceptions
    if isinstance(error, ApplicationError):
        _handle_application_error(error, context)
        return

    # Handle unexpected errors (infrastructure, programming errors, etc.)
    _handle_unexpected_error(error, context)


def _handle_domain_error(error: DomainError, context: dict[str, Any]) -> None:
    """Handle domain exceptions with user-friendly messages."""
    # Extract error information
    message = error.message if hasattr(error, "message") else str(error)
    details = error.details if hasattr(error, "details") else {}

    # Build user-friendly message
    user_message = f"[bold red]Error:[/bold red] {message}"

    # Add context-specific information if available
    if context:
        context_info = ", ".join(f"{k}: {v}" for k, v in context.items())
        user_message += f"\n[dim]Context: {context_info}[/dim]"

    # Add details if available
    if details:
        details_text = "\n".join(f"  • {k}: {v}" for k, v in details.items())
        user_message += f"\n\n[dim]Details:[/dim]\n{details_text}"

    console.print(Panel(user_message, border_style="red", title="Domain Error"))


def _handle_application_error(error: ApplicationError, context: dict[str, Any]) -> None:
    """Handle application exceptions with user-friendly messages."""
    message = error.message if hasattr(error, "message") else str(error)
    cause = error.cause if hasattr(error, "cause") else None

    user_message = f"[bold yellow]Application Error:[/bold yellow] {message}"

    if cause:
        user_message += f"\n[dim]Caused by: {type(cause).__name__}: {str(cause)}[/dim]"

    if context:
        context_info = ", ".join(f"{k}: {v}" for k, v in context.items())
        user_message += f"\n[dim]Context: {context_info}[/dim]"

    console.print(Panel(user_message, border_style="yellow", title="Application Error"))


def _handle_unexpected_error(error: Exception, context: dict[str, Any]) -> None:
    """Handle unexpected errors with user-friendly messages."""
    error_type = type(error).__name__
    error_message = str(error)

    user_message = (
        f"[bold red]Unexpected Error:[/bold red] {error_type}\n" f"[dim]{error_message}[/dim]"
    )

    if context:
        context_info = ", ".join(f"{k}: {v}" for k, v in context.items())
        user_message += f"\n[dim]Context: {context_info}[/dim]"

    user_message += "\n\n[dim]This is an unexpected error. Please report this issue with the error details above.[/dim]"

    console.print(Panel(user_message, border_style="red", title="Unexpected Error"))
