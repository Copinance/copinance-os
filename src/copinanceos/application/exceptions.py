"""Application layer exceptions.

These exceptions represent application-level errors that may wrap domain exceptions
or represent application-specific concerns like use case execution failures.
"""


class ApplicationError(Exception):
    """Base exception for all application layer errors."""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        """Initialize application exception.

        Args:
            message: Human-readable error message
            cause: Optional underlying exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.cause = cause
