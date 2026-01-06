"""Tool executor for executing tool calls from LLMs."""

from typing import Any

import structlog

from copinanceos.domain.models.tool_results import ToolResult
from copinanceos.domain.ports.tools import Tool

logger = structlog.get_logger(__name__)


class ToolExecutor:
    """Executor for tool calls from LLMs.

    Handles tool lookup, parameter validation, execution, and error handling.
    """

    def __init__(self, tools: list[Tool]) -> None:
        """Initialize tool executor with available tools.

        Args:
            tools: List of available tools
        """
        self._tools: dict[str, Tool] = {tool.get_name(): tool for tool in tools}
        logger.info("Initialized tool executor", tool_count=len(self._tools))

    async def execute_tool(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool by name.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Tool parameters

        Returns:
            ToolResult with execution outcome

        Raises:
            ValueError: If tool is not found
        """
        if tool_name not in self._tools:
            error_msg = f"Tool '{tool_name}' not found. Available tools: {list(self._tools.keys())}"
            logger.error(
                "Tool not found", tool_name=tool_name, available_tools=list(self._tools.keys())
            )
            return ToolResult(
                success=False,
                data=None,
                error=error_msg,
            )

        tool = self._tools[tool_name]
        logger.debug("Executing tool", tool_name=tool_name, parameters=kwargs)

        try:
            result = await tool.execute(**kwargs)
            logger.info(
                "Tool execution completed",
                tool_name=tool_name,
                success=result.success,
            )
            return result
        except Exception as e:
            logger.error("Tool execution failed", tool_name=tool_name, error=str(e))
            return ToolResult(
                success=False,
                data=None,
                error=str(e),
            )

    def get_tool(self, tool_name: str) -> Tool | None:
        """Get a tool by name.

        Args:
            tool_name: Name of the tool

        Returns:
            Tool if found, None otherwise
        """
        return self._tools.get(tool_name)

    def list_tools(self) -> list[str]:
        """List all available tool names.

        Returns:
            List of tool names
        """
        return list(self._tools.keys())
