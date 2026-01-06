"""Error handling utilities for infrastructure layer.

This module provides utilities to convert infrastructure errors to domain exceptions,
following the error handling strategy where infrastructure errors are converted to
domain exceptions before being propagated to the application layer.
"""

from typing import Any

import structlog

from copinanceos.domain.exceptions import (
    DataProviderError,
    DataProviderUnavailableError,
    DomainError,
)

logger = structlog.get_logger(__name__)


def convert_to_domain_exception(
    error: Exception,
    component: str,
    operation: str,
    context: dict[str, Any] | None = None,
) -> DomainError:
    """Convert an infrastructure error to a domain exception.

    This function follows the error handling strategy where infrastructure errors
    are converted to domain exceptions before being propagated to the application layer.

    Args:
        error: The infrastructure error to convert
        component: Name of the infrastructure component (e.g., "YFinanceProvider", "Cache")
        operation: Operation that failed (e.g., "get_quote", "get_fundamentals")
        context: Optional context information for logging

    Returns:
        Domain exception representing the error

    Examples:
        >>> try:
        ...     result = provider.get_quote("AAPL")
        ... except Exception as e:
        ...     raise convert_to_domain_exception(e, "YFinanceProvider", "get_quote")
    """
    error_message = str(error)
    error_type = type(error).__name__

    # Log the infrastructure error for debugging
    log_context = {
        "component": component,
        "operation": operation,
        "error_type": error_type,
        "error_message": error_message,
    }
    if context:
        log_context.update(context)

    logger.warning(
        "Infrastructure error converted to domain exception",
        **log_context,
        exc_info=True,
    )

    # Convert specific error types to appropriate domain exceptions
    if isinstance(error, DomainError):
        # Already a domain exception, return as-is
        return error

    # Check for common infrastructure error patterns
    error_lower = error_message.lower()

    # Network/connectivity errors
    if any(
        keyword in error_lower for keyword in ["connection", "timeout", "network", "unreachable"]
    ):
        return DataProviderUnavailableError(
            provider_name=component,
            details={
                "operation": operation,
                "error_type": error_type,
                "original_error": error_message,
            },
        )

    # Data provider errors (generic)
    return DataProviderError(
        provider_name=component,
        operation=operation,
        message=error_message,
        details={
            "error_type": error_type,
            "original_error": error_message,
        },
    )


def handle_infrastructure_error(
    error: Exception,
    component: str,
    operation: str,
    context: dict[str, Any] | None = None,
    default_return: Any = None,
) -> Any:
    """Handle infrastructure errors by converting to domain exceptions or returning default.

    This is a convenience function that either:
    1. Converts the error to a domain exception and re-raises it
    2. Returns a default value if provided

    Args:
        error: The infrastructure error to handle
        component: Name of the infrastructure component
        operation: Operation that failed
        context: Optional context information
        default_return: Optional default value to return instead of raising

    Returns:
        Default value if provided, otherwise raises domain exception

    Raises:
        DomainError: If default_return is None, converts and raises the error
    """
    domain_exception = convert_to_domain_exception(error, component, operation, context)

    if default_return is not None:
        logger.debug(
            "Infrastructure error handled with default return",
            component=component,
            operation=operation,
            default_return=default_return,
        )
        return default_return

    raise domain_exception
