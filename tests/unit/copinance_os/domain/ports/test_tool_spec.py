"""ToolSpec: declarative tool definitions, and the from_legacy/to_legacy_tool
adapters that let migration be incremental (see tool_spec.py's module docstring)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, Field

from copinance_os.core.pipeline.tools.tool_executor import ToolExecutor
from copinance_os.domain.models.pipeline.tool_results import ToolResult
from copinance_os.domain.ports.tool_spec import ToolSpec
from copinance_os.domain.ports.tools import Tool, ToolSchema


class _EchoTool(Tool):
    """A minimal legacy Tool: one required string, one optional int (default),
    one optional enum — enough surface to exercise every branch of the JSON
    Schema -> Pydantic synthesis in _args_model_from_json_schema."""

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name="echo",
            description="Echo the given arguments back.",
            parameters={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Instrument symbol"},
                    "limit": {"type": "integer", "description": "Max rows", "default": 5},
                    "side": {
                        "type": "string",
                        "description": "Side filter",
                        "enum": ["call", "put"],
                    },
                },
                "required": ["symbol"],
            },
        )

    def get_name(self) -> str:
        return "echo"

    def get_description(self) -> str:
        return "Echo the given arguments back."

    async def execute(self, **kwargs: Any) -> ToolResult[Any]:
        validated = self.validate_parameters(**kwargs)
        return ToolResult(success=True, data=validated)


class _FailingTool(_EchoTool):
    async def execute(self, **kwargs: Any) -> ToolResult[Any]:
        raise RuntimeError("boom")


def test_from_legacy_preserves_name_and_description() -> None:
    spec = ToolSpec.from_legacy(_EchoTool())
    assert spec.name == "echo"
    assert spec.description == "Echo the given arguments back."


def test_from_legacy_json_schema_marks_required_and_optional_correctly() -> None:
    spec = ToolSpec.from_legacy(_EchoTool())
    schema = spec.json_schema()
    assert schema["required"] == ["symbol"]
    assert schema["properties"]["symbol"]["type"] == "string"


def test_from_legacy_json_schema_carries_enum_values() -> None:
    spec = ToolSpec.from_legacy(_EchoTool())
    schema = spec.json_schema()
    # The curated wire_schema is used verbatim (see test_from_legacy_json_schema_is_the_curated_original) —
    # a plain enum list, not a Pydantic-regenerated anyOf/null union.
    assert schema["properties"]["side"]["enum"] == ["call", "put"]


def test_from_legacy_defaults_carry_through() -> None:
    spec = ToolSpec.from_legacy(_EchoTool())
    schema = spec.json_schema()
    assert schema["properties"]["limit"]["default"] == 5


def test_from_legacy_json_schema_is_the_curated_original_not_a_regeneration() -> None:
    """Regression: json_schema() used to always regenerate from args_model,
    which measured +34% larger token cost across the 25 builtin tools (95
    redundant "title" keys, every optional field wrapped in an anyOf/null
    union, additionalProperties: true leaking from extra="allow"). from_legacy
    must hand the tool's own curated schema to providers unchanged."""
    tool = _EchoTool()
    spec = ToolSpec.from_legacy(tool)
    assert spec.json_schema() == tool.get_schema().parameters


def test_from_legacy_json_schema_has_no_additional_properties_leak() -> None:
    spec = ToolSpec.from_legacy(_EchoTool())
    assert "additionalProperties" not in spec.json_schema()


def test_native_tool_spec_without_wire_schema_still_regenerates_from_args_model() -> None:
    """A hand-written native ToolSpec that never set wire_schema keeps the
    old regenerate-from-args_model fallback — from_legacy is the one path
    that must not use it, not json_schema() itself."""

    class NativeArgs(BaseModel):
        symbol: str = Field(..., description="Instrument symbol")

    async def _handler(**kwargs: Any) -> ToolResult[Any]:
        return ToolResult(success=True, data=kwargs)

    spec = ToolSpec(
        name="native", description="A native tool", args_model=NativeArgs, handler=_handler
    )
    schema = spec.json_schema()
    assert schema["properties"]["symbol"]["type"] == "string"
    assert "title" not in schema


@pytest.mark.asyncio
async def test_from_legacy_handler_executes_the_wrapped_tool() -> None:
    spec = ToolSpec.from_legacy(_EchoTool())
    result = await spec.handler(symbol="AAPL", side="call")
    assert result.success is True
    assert isinstance(result.data, dict)
    assert result.data["symbol"] == "AAPL"


@pytest.mark.asyncio
async def test_from_legacy_handler_drops_none_for_unset_optional_fields() -> None:
    """A synthesized args_model fills every unset optional field with an
    explicit None; the legacy tool's own validate_parameters was never written
    to accept None for a typed param (it expects "not provided", not "provided
    as null"). The handler must strip those Nones rather than pass them
    through — this is the exact case a naive `tool.execute(**kwargs)` breaks
    on for _EchoTool's optional `side` string param."""
    spec = ToolSpec.from_legacy(_EchoTool())
    result = await spec.handler(symbol="AAPL", limit=None, side=None)
    assert result.success is True
    # `limit` has a schema default (5) so the legacy validator fills it in
    # once dropped as unset; `side` has no default and is simply absent.
    assert result.data == {"symbol": "AAPL", "limit": 5}


@pytest.mark.asyncio
async def test_to_legacy_tool_validates_before_calling_the_handler() -> None:
    tool = ToolSpec.from_legacy(_EchoTool()).to_legacy_tool()
    with pytest.raises(Exception):  # noqa: B017 - pydantic ValidationError
        await tool.execute(side="not-a-valid-side")  # missing required `symbol` too


@pytest.mark.asyncio
async def test_to_legacy_tool_round_trips_through_tool_executor() -> None:
    """The whole point of to_legacy_tool: a ToolSpec must be a drop-in Tool for
    the existing ToolExecutor/tool-bundle pipeline, unchanged."""
    tool = ToolSpec.from_legacy(_EchoTool()).to_legacy_tool()
    executor = ToolExecutor([tool])

    result = await executor.execute_tool("echo", symbol="MSFT", limit=3)

    assert result.success is True
    # `side` was never provided and has no schema default — from_legacy's
    # handler must not forward it as an explicit None (see its docstring);
    # the legacy tool's own validate_parameters simply omits it, as before.
    assert result.data == {"symbol": "MSFT", "limit": 3}


@pytest.mark.asyncio
async def test_to_legacy_tool_surfaces_handler_exceptions_as_error_result_via_executor() -> None:
    tool = ToolSpec.from_legacy(_FailingTool()).to_legacy_tool()
    executor = ToolExecutor([tool])

    result = await executor.execute_tool("echo", symbol="MSFT")

    assert result.success is False
    assert "boom" in (result.error or "")


def test_to_legacy_tool_get_name_and_description_match_spec() -> None:
    spec = ToolSpec.from_legacy(_EchoTool())
    tool = spec.to_legacy_tool()
    assert tool.get_name() == spec.name
    assert tool.get_description() == spec.description


def test_tool_spec_policy_fields_default_sensibly() -> None:
    spec = ToolSpec.from_legacy(_EchoTool())
    assert spec.timeout_s == 20.0
    assert spec.cache_ttl_s is None
    assert spec.parallel_safe is True
    assert spec.max_result_tokens == 4000
    assert spec.tags == frozenset()
    assert spec.tabular_fields == frozenset()


def test_tool_spec_policy_fields_are_settable() -> None:
    spec = ToolSpec.from_legacy(_EchoTool())
    tuned = spec.model_copy(
        update={
            "timeout_s": 5.0,
            "cache_ttl_s": 10.0,
            "parallel_safe": False,
            "tags": frozenset({"market"}),
        }
    )
    assert tuned.timeout_s == 5.0
    assert tuned.cache_ttl_s == 10.0
    assert tuned.parallel_safe is False
    assert "market" in tuned.tags
