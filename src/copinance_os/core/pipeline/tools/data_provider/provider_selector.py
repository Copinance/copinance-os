"""Provider selector for routing tool calls to appropriate data providers."""

from collections.abc import Callable
from typing import Any, Generic, TypeVar

import structlog

from copinance_os.domain.ports.data_providers import DataProvider

logger = structlog.get_logger(__name__)

TProvider = TypeVar("TProvider", bound=DataProvider)


class ProviderSelector(Generic[TProvider]):
    """Selects appropriate provider for tool execution.

    This allows tools to use different providers for different operations,
    enabling scenarios like using one vendor for quotes and another for SEC filings.
    """

    def __init__(
        self,
        default_provider: TProvider,
        selection_strategy: Callable[[str, dict[str, Any]], TProvider] | None = None,
    ) -> None:
        """Initialize provider selector.

        Args:
            default_provider: Default provider to use when no specific selection is made
            selection_strategy: Optional function to select provider based on tool name and params
        """
        self._default_provider = default_provider
        self._selection_strategy = selection_strategy
        self._providers: dict[str, TProvider] = {}
        self._register_provider("default", default_provider)

    def register_provider(self, name: str, provider: TProvider) -> None:
        """Register a provider with a name.

        Args:
            name: Provider identifier
            provider: Provider instance
        """
        self._providers[name] = provider
        logger.debug("Registered provider", name=name, provider_type=type(provider).__name__)

    def get_provider(
        self,
        tool_name: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> TProvider:
        """Get appropriate provider for tool execution.

        Args:
            tool_name: Name of the tool being executed
            params: Tool parameters

        Returns:
            Selected provider instance
        """
        if self._selection_strategy:
            try:
                selected = self._selection_strategy(tool_name or "", params or {})
                if selected:
                    logger.debug(
                        "Selected provider via strategy",
                        tool_name=tool_name,
                        provider=selected.get_provider_name(),
                    )
                    return selected
            except Exception as e:
                logger.warning(
                    "Provider selection strategy failed, using default",
                    error=str(e),
                    tool_name=tool_name,
                )

        return self._default_provider

    def _register_provider(self, name: str, provider: TProvider) -> None:
        """Internal method to register provider."""
        self._providers[name] = provider


class MultiProviderSelector(Generic[TProvider]):
    """Manages multiple providers with capability-based selection.

    Allows tools to select providers based on their capabilities,
    enabling different providers for different operations.
    """

    def __init__(self) -> None:
        """Initialize multi-provider selector."""
        self._providers: dict[str, TProvider] = {}
        self._capability_map: dict[str, list[str]] = {}  # capability -> provider names

    def register_provider(
        self,
        name: str,
        provider: TProvider,
        capabilities: list[str] | None = None,
    ) -> None:
        """Register a provider with optional capabilities.

        Args:
            name: Provider identifier
            provider: Provider instance
            capabilities: List of capabilities this provider supports
        """
        self._providers[name] = provider
        if capabilities:
            for capability in capabilities:
                if capability not in self._capability_map:
                    self._capability_map[capability] = []
                self._capability_map[capability].append(name)
        logger.debug(
            "Registered provider",
            name=name,
            provider_type=type(provider).__name__,
            capabilities=capabilities,
        )

    def get_provider_for_capability(self, capability: str) -> TProvider | None:
        """Get provider that supports a specific capability.

        Args:
            capability: Capability name (e.g., 'sec_filings', 'financial_statements')

        Returns:
            Provider instance or None if no provider supports the capability
        """
        if capability in self._capability_map:
            provider_names = self._capability_map[capability]
            if provider_names:
                provider_name = provider_names[0]  # Use first available
                return self._providers.get(provider_name)
        return None

    def get_provider(self, name: str) -> TProvider | None:
        """Get provider by name.

        Args:
            name: Provider identifier

        Returns:
            Provider instance or None if not found
        """
        return self._providers.get(name)

    def get_default_provider(self) -> TProvider | None:
        """Get default provider (first registered).

        Returns:
            Default provider instance or None
        """
        if self._providers:
            return next(iter(self._providers.values()))
        return None

    def list_providers(self) -> list[str]:
        """List all registered provider names.

        Returns:
            List of provider names
        """
        return list(self._providers.keys())
