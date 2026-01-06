"""Base classes for data provider tools."""

from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

import structlog

from copinanceos.domain.models.tool_results import ToolResult
from copinanceos.domain.ports.data_providers import DataProvider
from copinanceos.domain.ports.tools import Tool, ToolSchema
from copinanceos.infrastructure.cache import CacheManager

logger = structlog.get_logger(__name__)

TProvider = TypeVar("TProvider", bound=DataProvider)


class BaseDataProviderTool(Tool, Generic[TProvider]):
    """Base class for data provider tools with common functionality."""

    def __init__(
        self,
        provider: TProvider,
        cache_manager: CacheManager | None = None,
        use_cache: bool = True,
    ) -> None:
        """Initialize tool with data provider.

        Args:
            provider: Data provider instance
            cache_manager: Optional cache manager for caching tool results
            use_cache: Whether to use caching (default: True if cache_manager is provided)
        """
        self._provider: TProvider = provider
        self._cache_manager = cache_manager
        self._use_cache = use_cache and cache_manager is not None

    async def _execute_with_cache(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        """Execute tool with caching support.

        This method should be called by subclasses in their execute method.
        It handles cache lookup and storage.

        Args:
            force_refresh: If True, bypass cache and fetch fresh data
            **kwargs: Tool parameters

        Returns:
            ToolResult from cache or execution
        """
        tool_name = self.get_name()

        # Check cache if enabled and not forcing refresh
        if self._use_cache and not force_refresh and self._cache_manager is not None:
            try:
                logger.debug(
                    "Checking cache",
                    tool_name=tool_name,
                    cache_enabled=self._use_cache,
                    has_cache_manager=self._cache_manager is not None,
                )
                cache_entry = await self._cache_manager.get(tool_name, **kwargs)
                if cache_entry:
                    # Return cached data with warning
                    age = datetime.now(UTC) - cache_entry.cached_at
                    age_minutes = int(age.total_seconds() / 60)

                    logger.info(
                        "Returning cached data",
                        tool_name=tool_name,
                        cached_at=cache_entry.cached_at.isoformat(),
                        age_minutes=age_minutes,
                    )

                    return self._create_success_result(
                        data=cache_entry.data,
                        metadata={
                            **cache_entry.metadata,
                            "cached": True,
                            "cached_at": cache_entry.cached_at.isoformat(),
                            "cache_warning": f"Data cached {age_minutes} minutes ago. Use --refresh to get latest data.",
                        },
                    )
            except Exception as e:
                logger.warning("Cache lookup failed, proceeding with execution", error=str(e))

        # Execute tool (subclass should implement _execute_impl)
        result = await self._execute_impl(**kwargs)

        # Cache successful results
        if self._use_cache and result.success and self._cache_manager is not None:
            try:
                logger.debug(
                    "Caching result",
                    tool_name=tool_name,
                    success=result.success,
                    has_data=result.data is not None,
                )
                await self._cache_manager.set(
                    tool_name,
                    data=result.data,
                    metadata=result.metadata,
                    **kwargs,
                )
                logger.info("Cached tool result", tool_name=tool_name)
            except Exception as e:
                logger.warning("Failed to cache result", error=str(e), tool_name=tool_name)
        elif not self._use_cache:
            logger.debug("Caching disabled", tool_name=tool_name)
        elif self._cache_manager is None:
            logger.debug("No cache manager available", tool_name=tool_name)

        return result

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        """Execute tool implementation.

        Subclasses should implement this method with their actual execution logic.
        This method is called by _execute_with_cache.

        Args:
            **kwargs: Tool parameters

        Returns:
            ToolResult from execution
        """
        raise NotImplementedError("Subclasses must implement _execute_impl")

    def _create_success_result(
        self,
        data: Any,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Create a successful tool result.

        Args:
            data: Result data
            metadata: Optional metadata to include

        Returns:
            ToolResult with success=True
        """
        base_metadata = {"provider": self._provider.get_provider_name()}
        if metadata:
            base_metadata.update(metadata)
        return ToolResult(success=True, data=data, metadata=base_metadata)

    def _create_error_result(
        self,
        error: Exception | str,
        metadata: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Create an error tool result.

        Args:
            error: Error exception or message
            metadata: Optional metadata to include

        Returns:
            ToolResult with success=False
        """
        error_message = str(error) if isinstance(error, Exception) else error
        return ToolResult(
            success=False,
            data=None,
            error=error_message,
            metadata=metadata or {},
        )

    def _serialize_data(self, data: Any) -> Any:
        """Serialize data to JSON-compatible format.

        Args:
            data: Data to serialize

        Returns:
            Serialized data
        """
        if hasattr(data, "model_dump"):
            return data.model_dump()
        if isinstance(data, list):
            return [self._serialize_data(item) for item in data]
        if isinstance(data, dict):
            return {k: self._serialize_data(v) for k, v in data.items()}
        return data

    def _build_schema(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        returns: dict[str, Any] | None = None,
    ) -> ToolSchema:
        """Build a tool schema with common structure.

        Args:
            name: Tool name
            description: Tool description
            parameters: Parameter schema
            returns: Return schema (optional)

        Returns:
            ToolSchema instance
        """
        return ToolSchema(
            name=name,
            description=description,
            parameters={
                "type": "object",
                "properties": parameters.get("properties", {}),
                "required": parameters.get("required", []),
            },
            returns=returns,
        )
