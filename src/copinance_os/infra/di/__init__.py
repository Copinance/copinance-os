"""Container modules for dependency injection.

This package contains modular container configurations split by responsibility:
- storage: Storage backend configuration
- repositories: Repository providers
- services: Domain service providers
- data_providers: Data provider providers
- use_cases: Use case providers

Exports are resolved lazily via ``__getattr__`` so that importing this package
does not eagerly import ``container.py`` (and transitively all DI sub-modules).
The heavy vendor libraries only load when a provider is first resolved at runtime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from copinance_os.infra.di.container import (
        Container,
        create_container,
    )

__all__ = [
    "Container",
    "create_container",
]

_EXPORTS = frozenset(__all__)


def __getattr__(name: str) -> Any:
    if name in _EXPORTS:
        from copinance_os.infra.di.container import (  # noqa: PLC0415
            Container,
            create_container,
        )

        # Cache in globals so subsequent accesses are O(1) attribute lookups
        g = globals()
        g["Container"] = Container
        g["create_container"] = create_container
        return g[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
