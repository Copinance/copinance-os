"""Tool interface for wrapping data providers and other functions as LLM tools."""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from copinanceos.domain.models.tool_results import ToolResult


class ToolParameter(BaseModel):
    """Schema for a tool parameter."""

    name: str = Field(..., description="Parameter name")
    type: str = Field(
        ..., description="Parameter type (string, number, integer, boolean, array, object)"
    )
    description: str = Field(..., description="Parameter description")
    required: bool = Field(default=True, description="Whether parameter is required")
    enum: list[Any] | None = Field(default=None, description="Allowed values if parameter is enum")


class ToolSchema(BaseModel):
    """JSON Schema for a tool (compatible with OpenAI/Gemini function calling)."""

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    parameters: dict[str, Any] = Field(..., description="JSON Schema for parameters")
    returns: dict[str, Any] | None = Field(default=None, description="JSON Schema for return value")


class Tool(ABC):
    """Base interface for tools that can be used by LLMs or independently.

    Tools are self-describing functions that wrap data providers or other
    functionality. They provide:
    - Schema definition (for LLM function calling)
    - Validation
    - Execution
    - Error handling
    """

    @abstractmethod
    def get_schema(self) -> ToolSchema:
        """Get JSON Schema for this tool.

        Returns:
            ToolSchema with name, description, and parameter definitions
        """
        pass

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult[Any]:
        """Execute the tool with given parameters.

        Args:
            **kwargs: Tool parameters (validated against schema)

        Returns:
            ToolResult[Any] with execution outcome

        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If tool execution fails
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Get the tool name.

        Returns:
            Tool name (should match schema name)
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """Get the tool description.

        Returns:
            Tool description
        """
        pass

    def validate_parameters(self, **kwargs: Any) -> dict[str, Any]:
        """Validate and normalize parameters.

        Args:
            **kwargs: Raw parameters

        Returns:
            Validated and normalized parameters (with defaults applied)

        Raises:
            ValueError: If parameters are invalid
        """
        schema = self.get_schema()
        validated: dict[str, Any] = {}

        # Extract parameter schema
        param_props = schema.parameters.get("properties", {})
        param_required = schema.parameters.get("required", [])

        # Apply defaults first
        for param_name, param_schema in param_props.items():
            if "default" in param_schema and param_name not in kwargs:
                validated[param_name] = param_schema["default"]

        # Validate required parameters
        for param_name in param_required:
            if param_name not in kwargs and param_name not in validated:
                raise ValueError(f"Missing required parameter: {param_name}")

        # Validate and normalize each provided parameter
        for param_name, param_value in kwargs.items():
            if param_name not in param_props:
                # Allow extra parameters but warn
                validated[param_name] = param_value
                continue

            param_schema = param_props[param_name]
            param_type = param_schema.get("type")

            # Type validation
            if param_type == "string" and not isinstance(param_value, str):
                raise ValueError(f"Parameter {param_name} must be a string")
            elif param_type == "number" and not isinstance(param_value, (int, float)):
                raise ValueError(f"Parameter {param_name} must be a number")
            elif param_type == "integer" and not isinstance(param_value, int):
                raise ValueError(f"Parameter {param_name} must be an integer")
            elif param_type == "boolean" and not isinstance(param_value, bool):
                raise ValueError(f"Parameter {param_name} must be a boolean")
            elif param_type == "array" and not isinstance(param_value, list):
                raise ValueError(f"Parameter {param_name} must be an array")

            # Enum validation
            if "enum" in param_schema:
                if param_value not in param_schema["enum"]:
                    raise ValueError(
                        f"Parameter {param_name} must be one of {param_schema['enum']}. "
                        f"You provided: {param_value}"
                    )

            validated[param_name] = param_value

        return validated
