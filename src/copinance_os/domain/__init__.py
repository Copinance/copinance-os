"""
Domain layer - Core business logic and entities.

This layer contains the core domain models, value objects, and domain services.
It has no dependencies on other layers and represents the heart of the business logic.
"""

from copinance_os.domain.exceptions import (
    AnalysisExecutionError,
    DataProviderError,
    DataProviderUnavailableError,
    DomainError,
    EntityNotFoundError,
    ExecutorNotFoundError,
    InvalidStockSymbolError,
    ProfileNotFoundError,
    RetryableExecutionError,
    StockNotFoundError,
    ValidationError,
)
from copinance_os.domain.services import ProfileManagementService
from copinance_os.domain.validation import StockSymbolValidator

__all__ = [
    # Exceptions
    "DomainError",
    "EntityNotFoundError",
    "StockNotFoundError",
    "ProfileNotFoundError",
    "ValidationError",
    "InvalidStockSymbolError",
    "AnalysisExecutionError",
    "ExecutorNotFoundError",
    "DataProviderError",
    "DataProviderUnavailableError",
    "RetryableExecutionError",
    # Domain Services
    "ProfileManagementService",
    # Domain Validators
    "StockSymbolValidator",
]
