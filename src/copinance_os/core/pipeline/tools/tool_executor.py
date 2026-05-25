"""Tool executor for executing tool calls from LLMs."""

import time
from typing import Any

import structlog

from copinance_os.core.progress.emit import maybe_emit_progress
from copinance_os.core.progress.redaction import summarize_for_tool_args, summarize_tool_result
from copinance_os.domain.models.pipeline.agent_progress import ToolFinishedEvent, ToolStartedEvent
from copinance_os.domain.models.pipeline.tool_results import ToolResult
from copinance_os.domain.ports.progress import ProgressSink
from copinance_os.domain.ports.tools import Tool

logger = structlog.get_logger(__name__)


class ToolExecutor:
    """Executor for tool calls from LLMs.

    Handles tool lookup, parameter validation, execution, and error handling.
    """

    def __init__(
        self,
        tools: list[Tool],
        *,
        progress_sink: ProgressSink | None = None,
        run_id: str | None = None,
    ) -> None:
        """Initialize tool executor with available tools.

        Args:
            tools: List of available tools
            progress_sink: Optional sink for structured progress events
            run_id: Correlates progress events for this agent run
        """
        self._tools: dict[str, Tool] = {tool.get_name(): tool for tool in tools}
        self._progress_sink = progress_sink
        self._run_id = run_id
        logger.info("Initialized tool executor", tool_count=len(self._tools))

    async def execute_tool(
        self,
        tool_name: str,
        *,
        progress_iteration: int | None = None,
        progress_call_index: int | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a tool by name.

        Args:
            tool_name: Name of the tool to execute
            progress_iteration: Optional 1-based agent iteration for progress streams
            progress_call_index: Optional tool call index within the iteration
            **kwargs: Tool parameters

        Returns:
            ToolResult with execution outcome

        Raises:
            ValueError: If tool is not found
        """
        rid = self._run_id
        sink = self._progress_sink
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

        args_summary = summarize_for_tool_args(kwargs)
        if sink is not None and rid is not None:
            await maybe_emit_progress(
                sink,
                ToolStartedEvent(
                    run_id=rid,
                    tool_name=tool_name,
                    args_summary=args_summary,
                    iteration=progress_iteration,
                    call_index=progress_call_index,
                ),
            )

        t0 = time.monotonic()
        try:
            result = await tool.execute(**kwargs)
            elapsed_ms = (time.monotonic() - t0) * 1000.0
            logger.info(
                "Tool execution completed",
                tool_name=tool_name,
                success=result.success,
            )
            if sink is not None and rid is not None:
                summary = summarize_tool_result(
                    result.success, result.data, result.error if not result.success else None
                )
                await maybe_emit_progress(
                    sink,
                    ToolFinishedEvent(
                        run_id=rid,
                        tool_name=tool_name,
                        success=result.success,
                        duration_ms=elapsed_ms,
                        result_summary=summary,
                    ),
                )
            return result
        except Exception as e:
            elapsed_ms = (time.monotonic() - t0) * 1000.0
            logger.error("Tool execution failed", tool_name=tool_name, error=str(e))
            if sink is not None and rid is not None:
                await maybe_emit_progress(
                    sink,
                    ToolFinishedEvent(
                        run_id=rid,
                        tool_name=tool_name,
                        success=False,
                        duration_ms=elapsed_ms,
                        result_summary=summarize_tool_result(False, None, str(e)),
                    ),
                )
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
