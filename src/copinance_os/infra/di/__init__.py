"""Container modules for dependency injection.

This package contains modular container configurations split by responsibility:
- storage: Storage backend configuration
- repositories: Repository providers
- services: Domain service providers
- data_providers: Data provider providers
- use_cases: Use case providers
"""

from copinance_os.infra.di.container import (
    Container,
    container,
    get_container,
    reset_container,
    set_container,
)

__all__ = [
    "Container",
    "container",
    "get_container",
    "set_container",
    "reset_container",
]
