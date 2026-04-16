"""Profile-only use case configuration.

Intentionally imports nothing from the AI, market-data, or analysis stacks so that
``copinance profile <cmd>`` never pays the ~2 s cold-import cost of openai / pandas /
edgar / QuantLib.  Only lightweight domain models and pydantic providers are touched.
"""

from __future__ import annotations

from dependency_injector import providers


def configure_profile_use_cases(
    profile_repository: providers.Provider,
    current_profile: providers.Provider,
    profile_management_service: providers.Provider,
) -> dict[str, providers.Provider]:
    """Profile-only use cases (no market, fundamentals, or LLM dependencies)."""
    from copinance_os.research.workflows.profile import (  # noqa: PLC0415
        CreateProfileUseCase,
        DeleteProfileUseCase,
        GetCurrentProfileUseCase,
        GetProfileUseCase,
        ListProfilesUseCase,
        SetCurrentProfileUseCase,
    )

    create_profile_use_case = providers.Factory(
        CreateProfileUseCase,
        profile_repository=profile_repository,
        profile_service=profile_management_service,
        current_profile=current_profile,
    )

    get_current_profile_use_case = providers.Factory(
        GetCurrentProfileUseCase,
        profile_repository=profile_repository,
        current_profile=current_profile,
    )

    set_current_profile_use_case = providers.Factory(
        SetCurrentProfileUseCase,
        profile_repository=profile_repository,
        profile_service=profile_management_service,
        current_profile=current_profile,
    )

    delete_profile_use_case = providers.Factory(
        DeleteProfileUseCase,
        profile_repository=profile_repository,
        profile_service=profile_management_service,
        current_profile=current_profile,
    )

    get_profile_use_case = providers.Factory(
        GetProfileUseCase,
        profile_repository=profile_repository,
    )

    list_profiles_use_case = providers.Factory(
        ListProfilesUseCase,
        profile_repository=profile_repository,
    )

    return {
        "create_profile_use_case": create_profile_use_case,
        "get_current_profile_use_case": get_current_profile_use_case,
        "set_current_profile_use_case": set_current_profile_use_case,
        "delete_profile_use_case": delete_profile_use_case,
        "get_profile_use_case": get_profile_use_case,
        "list_profiles_use_case": list_profiles_use_case,
    }
