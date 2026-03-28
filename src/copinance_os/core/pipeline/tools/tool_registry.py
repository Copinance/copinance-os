"""Tool registry for managing and discovering tools."""

from typing import Any

import structlog

from copinance_os.domain.ports.tools import Tool

logger = structlog.get_logger(__name__)


class ToolRegistry:
    """Registry for managing tools.

    Provides tool discovery, registration, and lookup functionality.
    Tools can be registered and retrieved by name.
    """

    def __init__(self) -> None:
        """Initialize empty tool registry."""
        self._tools: dict[str, Tool] = {}
        logger.info("Initialized tool registry")

    def register(self, tool: Tool) -> None:
        """Register a tool.

        Args:
            tool: Tool to register

        Raises:
            ValueError: If tool with same name already exists
        """
        tool_name = tool.get_name()
        if tool_name in self._tools:
            raise ValueError(f"Tool '{tool_name}' is already registered")
        self._tools[tool_name] = tool
        logger.info("Registered tool", tool_name=tool_name)

    def register_many(self, tools: list[Tool]) -> None:
        """Register multiple tools.

        Args:
            tools: List of tools to register

        Raises:
            ValueError: If any tool name conflicts
        """
        for tool in tools:
            self.register(tool)

    def get(self, name: str) -> Tool | None:
        """Get a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool if found, None otherwise
        """
        return self._tools.get(name)

    def get_all(self) -> dict[str, Tool]:
        """Get all registered tools.

        Returns:
            Dictionary mapping tool names to tools
        """
        return self._tools.copy()

    def list_tools(self) -> list[str]:
        """List all registered tool names.

        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def get_schemas(self) -> list[dict[str, Any]]:
        """Get JSON schemas for all registered tools.

        Returns:
            List of tool schemas in JSON format
        """
        return [tool.get_schema().model_dump() for tool in self._tools.values()]

    def unregister(self, name: str) -> bool:
        """Unregister a tool.

        Args:
            name: Tool name to unregister

        Returns:
            True if tool was found and removed, False otherwise
        """
        if name in self._tools:
            del self._tools[name]
            logger.info("Unregistered tool", tool_name=name)
            return True
        return False

    def clear(self) -> None:
        """Clear all registered tools."""
        self._tools.clear()
        logger.info("Cleared tool registry")
