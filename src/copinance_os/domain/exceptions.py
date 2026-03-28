"""Domain-specific exceptions for business logic errors.

These exceptions represent business rule violations and domain errors,
distinct from technical/infrastructure errors. They should be caught
and handled appropriately at the application layer.
"""


class DomainError(Exception):
    """Base exception for all domain errors."""

    def __init__(self, message: str, details: dict[str, str] | None = None) -> None:
        """Initialize domain exception.

        Args:
            message: Human-readable error message
            details: Optional dictionary with additional error details
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class EntityNotFoundError(DomainError):
    """Raised when a requested entity is not found."""

    def __init__(
        self, entity_type: str, identifier: str, details: dict[str, str] | None = None
    ) -> None:
        """Initialize entity not found error.

        Args:
            entity_type: Type of entity (e.g., "Stock", "Job")
            identifier: Identifier that was searched for
            details: Optional additional details
        """
        message = f"{entity_type} with identifier '{identifier}' not found"
        super().__init__(message, details)
        self.entity_type = entity_type
        self.identifier = identifier


class StockNotFoundError(EntityNotFoundError):
    """Raised when a stock is not found."""

    def __init__(self, symbol: str, details: dict[str, str] | None = None) -> None:
        """Initialize stock not found error.

        Args:
            symbol: Stock symbol that was not found
            details: Optional additional details
        """
        super().__init__("Stock", symbol, details)
        self.symbol = symbol


class ProfileNotFoundError(EntityNotFoundError):
    """Raised when an analysis profile is not found."""

    def __init__(self, profile_id: str, details: dict[str, str] | None = None) -> None:
        """Initialize profile not found error.

        Args:
            profile_id: Profile ID that was not found
            details: Optional additional details
        """
        super().__init__("AnalysisProfile", profile_id, details)
        self.profile_id = profile_id


class ValidationError(DomainError):
    """Raised when domain validation fails."""

    def __init__(self, field: str, message: str, details: dict[str, str] | None = None) -> None:
        """Initialize validation error.

        Args:
            field: Field name that failed validation
            message: Validation error message
            details: Optional additional details
        """
        super().__init__(f"Validation failed for field '{field}': {message}", details)
        self.field = field


class InvalidStockSymbolError(ValidationError):
    """Raised when a stock symbol is invalid."""

    def __init__(
        self, symbol: str, reason: str | None = None, details: dict[str, str] | None = None
    ) -> None:
        """Initialize invalid stock symbol error.

        Args:
            symbol: Invalid stock symbol
            reason: Optional reason why it's invalid
            details: Optional additional details
        """
        message = f"Invalid stock symbol '{symbol}'"
        if reason:
            message += f": {reason}"
        super().__init__("symbol", message, details)
        self.symbol = symbol
        self.reason = reason


class AnalysisExecutionError(DomainError):
    """Raised when an analysis execution fails."""

    def __init__(
        self,
        execution_type: str,
        message: str,
        job_id: str | None = None,
        details: dict[str, str] | None = None,
    ) -> None:
        """Initialize analysis execution error.

        Args:
            execution_type: Type of analysis that failed
            message: Error message
            job_id: Optional job ID
            details: Optional additional details
        """
        super().__init__(f"Analysis '{execution_type}' execution failed: {message}", details)
        self.execution_type = execution_type
        self.job_id = job_id


class ExecutorNotFoundError(DomainError):
    """Raised when no executor is found for the job's execution type."""

    def __init__(self, execution_type: str, details: dict[str, str] | None = None) -> None:
        """Initialize executor not found error.

        Args:
            execution_type: Execution type that was not found
            details: Optional additional details
        """
        message = f"No executor found for execution type: {execution_type}"
        super().__init__(message, details)
        self.execution_type = execution_type


class DataProviderError(DomainError):
    """Raised when a data provider operation fails."""

    def __init__(
        self,
        provider_name: str,
        operation: str,
        message: str,
        details: dict[str, str] | None = None,
    ) -> None:
        """Initialize data provider error.

        Args:
            provider_name: Name of the data provider
            operation: Operation that failed (e.g., "get_quote", "get_fundamentals")
            message: Error message
            details: Optional additional details
        """
        super().__init__(
            f"Data provider '{provider_name}' failed during '{operation}': {message}",
            details,
        )
        self.provider_name = provider_name
        self.operation = operation


class DataProviderUnavailableError(DataProviderError):
    """Raised when a data provider is unavailable."""

    def __init__(self, provider_name: str, details: dict[str, str] | None = None) -> None:
        """Initialize data provider unavailable error.

        Args:
            provider_name: Name of the unavailable provider
            details: Optional additional details
        """
        super().__init__(provider_name, "is_available", "Provider is not available", details)


class RetryableExecutionError(DomainError):
    """Raised for transient failures where repeating the same request may succeed.

    Used by the job runner for optional bounded retries on idempotent analysis steps.
    """

    def __init__(self, message: str, details: dict[str, str] | None = None) -> None:
        super().__init__(message, details)
