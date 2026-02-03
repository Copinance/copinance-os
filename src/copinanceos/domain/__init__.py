"""
Domain layer - Core business logic and entities.

This layer contains the core domain models, value objects, and domain services.
It has no dependencies on other layers and represents the heart of the business logic.
"""

from copinanceos.domain.exceptions import (
    DataProviderError,
    DataProviderUnavailableError,
    DomainError,
    EntityNotFoundError,
    InvalidStockSymbolError,
    ProfileNotFoundError,
    StockNotFoundError,
    ValidationError,
    WorkflowExecutionError,
    WorkflowNotFoundError,
)
from copinanceos.domain.services import ProfileManagementService
from copinanceos.domain.validation import StockSymbolValidator

__all__ = [
    # Exceptions
    "DomainError",
    "EntityNotFoundError",
    "StockNotFoundError",
    "ProfileNotFoundError",
    "ValidationError",
    "InvalidStockSymbolError",
    "WorkflowExecutionError",
    "WorkflowNotFoundError",
    "DataProviderError",
    "DataProviderUnavailableError",
    # Domain Services
    "ProfileManagementService",
    # Domain Validators
    "StockSymbolValidator",
]
