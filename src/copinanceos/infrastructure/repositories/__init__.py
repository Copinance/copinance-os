"""Repository implementations package.

This package provides storage-agnostic repository implementations organized by entity type.
Each repository uses the Storage interface defined in the domain layer, hiding the
underlying storage implementation. The storage technology is not exposed to consumers.

Structure:
- storage/ - Storage backend implementations and factory (must implement domain.ports.storage.Storage)
- stock/ - Stock repository implementation
- profile/ - Research profile repository implementation

All repositories depend on the Storage interface, following the Dependency Inversion Principle.
The storage factory ensures implementation details are hidden.
"""

from copinanceos.infrastructure.repositories.profile import (
    ResearchProfileRepositoryImpl,
)
from copinanceos.infrastructure.repositories.stock import StockRepositoryImpl

__all__ = [
    "StockRepositoryImpl",
    "ResearchProfileRepositoryImpl",
]
