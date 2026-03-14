"""Repository container configuration."""

from dependency_injector import providers

from copinanceos.infrastructure.repositories import (
    AnalysisProfileRepositoryImpl,
    StockRepositoryImpl,
)
from copinanceos.infrastructure.repositories.profile import CurrentProfile


def configure_repositories(storage_backend: providers.Provider) -> dict[str, providers.Provider]:
    """Configure repository providers.

    Args:
        storage_backend: Storage backend provider

    Returns:
        Dictionary of repository providers
    """
    return {
        "stock_repository": providers.Singleton(
            StockRepositoryImpl,
            storage=storage_backend,
        ),
        "profile_repository": providers.Singleton(
            AnalysisProfileRepositoryImpl,
            storage=storage_backend,
        ),
        "current_profile": providers.Singleton(CurrentProfile),
    }
