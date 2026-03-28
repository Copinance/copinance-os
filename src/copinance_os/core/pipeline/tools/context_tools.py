"""Context tools: current date/time for LLM use (no external data provider)."""

from datetime import UTC, datetime
from typing import Any

from copinance_os.domain.models.tool_results import ToolResult
from copinance_os.domain.ports.tools import Tool, ToolSchema


class GetCurrentDateTool(Tool):
    """Tool that returns the current date and timezone for analysis context.

    Use this when you need to know today's date for relative ranges (e.g. 'last year',
    'trailing 12 months'). No parameters required; returns fresh date at call time.
    """

    def get_name(self) -> str:
        return "get_current_date"

    def get_description(self) -> str:
        return (
            "Get the current date and timezone (UTC) for use in relative date ranges "
            "(e.g. 'last year', 'trailing 12 months'). Call this when you need today's date."
        )

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "type": "object",
                "properties": {},
                "required": [],
            },
            returns={
                "type": "object",
                "description": "Current date and timezone",
                "properties": {
                    "current_date": {"type": "string", "description": "Today's date (YYYY-MM-DD)"},
                    "timezone": {"type": "string", "description": "Timezone (UTC)"},
                    "timestamp_iso": {"type": "string", "description": "Full ISO timestamp"},
                },
            },
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        now = datetime.now(UTC)
        return ToolResult(
            success=True,
            data={
                "current_date": now.date().isoformat(),
                "timezone": "UTC",
                "timestamp_iso": now.isoformat(),
            },
            metadata={},
        )
