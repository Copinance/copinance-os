"""Workflow result data models."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


# Base result wrapper for tool results
class ToolResult(BaseModel, Generic[T]):
    """Result from tool execution with success/error handling."""

    success: bool = Field(..., description="Whether tool execution succeeded")
    data: T | None = Field(default=None, description="Tool execution result data")
    error: str | None = Field(default=None, description="Error message if execution failed")
    metadata: Any = Field(default_factory=dict, description="Additional metadata")
