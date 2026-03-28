"""Domain service container configuration."""

from dependency_injector import providers

from copinance_os.domain.services import ProfileManagementService


def configure_services(
    profile_repository: providers.Provider,
) -> dict[str, providers.Provider]:
    """Configure domain service providers.

    Args:
        profile_repository: Analysis profile repository provider

    Returns:
        Dictionary of domain service providers
    """
    return {
        "profile_management_service": providers.Factory(
            ProfileManagementService,
            profile_repository=profile_repository,
        ),
    }
