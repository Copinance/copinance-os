"""Storage backend implementations and factory for repositories.

This package provides implementations of the Storage interface defined in
the domain layer. Storage backends handle the actual persistence mechanism
while repositories provide the domain-specific interface.

The factory pattern ensures that storage implementation details are hidden
from the rest of the application. All storage implementations must conform
to the Storage interface defined in copinance_os.domain.ports.storage.
"""

from copinance_os.data.repositories.storage.factory import (
    StorageType,
    create_storage,
    get_default_storage,
)

__all__ = ["StorageType", "create_storage", "get_default_storage"]
