"""``ToolSpec`` — declarative tool definitions, and the two adapters that let it
migrate the existing 25 copinance-os tools + 6 app-owned tools incrementally
rather than all at once.

Replaces the 4-abstract-method ``Tool`` ABC + hand-written ``ToolSchema`` +
hand-rolled ``Tool.validate_parameters`` type-checker with one Pydantic model
for validation — ``args_model.model_validate(raw_args)`` happens once, instead
of being re-implemented by each ``Tool`` subclass. The *wire* schema (what
providers actually see) is a separate concern: a hand-written native
``ToolSpec`` can let ``json_schema()`` derive it from ``args_model``, but
``from_legacy`` sets ``wire_schema`` explicitly to the tool's own curated
``ToolSchema.parameters`` rather than regenerating one — see ``ToolSpec.wire_schema``'s
docstring for why (regenerating measured +34% larger token cost on the 25
builtin tools).

Migration is incremental, not a rewrite:

- ``ToolSpec.from_legacy(tool)`` wraps an existing ``Tool`` — the args model is
  synthesized from ``tool.get_schema()`` (see ``_args_model_from_json_schema``)
  purely for *validation*, the wire schema stays the tool's own, and the
  handler calls ``tool.execute(**kwargs)`` — so every existing tool gets a
  ``ToolSpec`` for free, with the exact validation behavior it had before
  (schema-synthesized fields don't re-implement the checks
  ``Tool.validate_parameters`` already does — that still runs inside
  ``tool.execute``). Individual tools convert to a native ``ToolSpec`` (a
  hand-written ``args_model``, tighter validation, ``timeout_s``/
  ``cache_ttl_s``/``tags`` set deliberately rather than defaulted) as they're
  touched.
- ``ToolSpec.to_legacy_tool()`` wraps a ``ToolSpec`` back into a ``Tool``, so
  it can be handed to the *existing* ``ToolExecutor``/``collect_question_driven_tools``
  pipeline unchanged. This is what makes "day one, nothing breaks" true — a
  bundle can mix legacy ``Tool``s and native ``ToolSpec``s (via this adapter)
  in the same list, and callers don't need to know which is which.

``ToolRuntime`` (parallel execution, per-tool timeout, wall-clock deadline,
Redis-backed per-tool TTL cache, single-flight dedupe, metrics) is the next
piece to land on top of this — see the "faster, more reliable AI tool system"
design doc, Phase 1. This module is the declarative layer that runtime will
read policy off; it does not itself change how tools execute yet.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

from copinance_os.domain.models.pipeline.tool_results import ToolResult
from copinance_os.domain.ports.tools import Tool, ToolSchema

_JSON_SCHEMA_TYPE_MAP: dict[str, type] = {
    "string": str,
    "number": float,
    "integer": int,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _python_type_for(param_schema: dict[str, Any]) -> Any:
    enum_vals = param_schema.get("enum")
    if enum_vals:
        return Literal[tuple(enum_vals)]
    return _JSON_SCHEMA_TYPE_MAP.get(param_schema.get("type", ""), Any)


def _args_model_from_json_schema(tool_name: str, schema: ToolSchema) -> type[BaseModel]:
    """Synthesize a Pydantic args model from a legacy ``Tool``'s ``ToolSchema``.

    Best-effort, not a tightening of validation: a ``from_legacy``-derived
    model exists so every legacy tool has *an* ``args_model`` (so
    ``args_model.model_json_schema()`` is always a valid source for the
    schema apps.LLM providers send), not to replace ``Tool.validate_parameters``
    — that still runs inside the wrapped ``tool.execute()`` call. Unknown JSON
    Schema types fall back to ``Any`` rather than rejecting the tool.
    """
    properties: dict[str, Any] = schema.parameters.get("properties", {})
    required: set[str] = set(schema.parameters.get("required", []))

    fields: dict[str, Any] = {}
    for name, param_schema in properties.items():
        py_type = _python_type_for(param_schema)
        description = param_schema.get("description", "")
        if name in required:
            fields[name] = (py_type, Field(..., description=description))
        else:
            default = param_schema.get("default", None)
            fields[name] = (py_type | None, Field(default=default, description=description))

    model_name = "".join(part.capitalize() for part in tool_name.split("_")) + "Args"
    return create_model(
        model_name,
        __config__=ConfigDict(extra="allow"),  # legacy tools accept unknown kwargs today
        **fields,
    )


class ToolSpec(BaseModel):
    """Declarative tool definition — see module docstring."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[..., Awaitable[ToolResult[Any]]]
    # The schema actually sent to providers. Defaults to None, meaning
    # json_schema() falls back to regenerating one from args_model — fine for
    # a hand-written native ToolSpec, but from_legacy sets this explicitly to
    # the tool's own curated ToolSchema.parameters. Regenerating from
    # args_model instead of using this measured +34% larger on the 25 builtin
    # tools (95 redundant "title" keys json_schema() doesn't strip, every
    # optional field turned into an anyOf/null union that also tells the
    # model it may pass null — which _handler then has to silently filter —
    # plus extra="allow" leaking out as additionalProperties: true). Wire and
    # validation schemas are allowed to diverge on purpose here: args_model
    # stays permissive for backward-compatible validation, wire_schema stays
    # exactly what the tool author curated for the model to read.
    wire_schema: dict[str, Any] | None = None
    timeout_s: float = 20.0
    cache_ttl_s: float | None = None
    # Caching is keyed on (name, args) only — no user/session dimension. A
    # tool whose result depends on ambient identity (e.g. one reading a
    # request-scoped ContextVar for "the current user" rather than taking it
    # as an argument, like apps/backend's get_watchlist_context) would leak
    # one user's result to another if cached. cache_ttl_s alone doesn't
    # protect against this — set cacheable=False explicitly for any such
    # tool; ToolRuntime checks this before ever calling into the cache.
    cacheable: bool = True
    parallel_safe: bool = True
    max_result_tokens: int = 4000
    tabular_fields: frozenset[str] = frozenset()
    tags: frozenset[str] = frozenset()

    def json_schema(self) -> dict[str, Any]:
        """OpenAI/Gemini/Anthropic-compatible parameter schema for this tool.

        Returns ``wire_schema`` verbatim when set (the curated schema
        ``from_legacy`` wraps) — see that field's docstring for why this
        matters. Only regenerates from ``args_model`` when no wire schema was
        ever set (a hand-written native ``ToolSpec`` that didn't provide one).
        """
        if self.wire_schema is not None:
            return self.wire_schema
        schema = self.args_model.model_json_schema()
        # Pydantic emits $defs for nested models / Literal enums bundled at top
        # level already for simple scalar+enum fields, so no $ref rewriting is
        # needed for the tool shapes this migrates today (flat scalar/array/enum
        # args) — revisit if a native ToolSpec ever needs a nested args model.
        schema.pop("title", None)
        return schema

    def to_tool_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters=self.json_schema(),
        )

    @classmethod
    def from_legacy(
        cls,
        tool: Tool,
        *,
        cacheable: bool = True,
        cache_ttl_s: float | None = None,
        tags: frozenset[str] = frozenset(),
    ) -> ToolSpec:
        """Wrap an existing ``Tool`` instance as a ``ToolSpec``.

        ``cacheable``/``cache_ttl_s``/``tags`` are the one place a caller can
        set tool-specific policy on an otherwise-generic wrap — e.g. a caller
        building specs for a tool that reads ambient per-user state (see
        ``ToolSpec.cacheable``'s docstring) passes ``cacheable=False`` here
        rather than relying on this module to know that tool's name.
        """
        schema = tool.get_schema()
        args_model = _args_model_from_json_schema(tool.get_name(), schema)

        async def _handler(**kwargs: Any) -> ToolResult[Any]:
            # The synthesized args_model fills every unset optional field with
            # an explicit None (Pydantic's optional-field default). Tool.
            # validate_parameters was never written to accept an explicit None
            # for a typed (non-nullable) param — it expects "not provided",
            # not "provided as null" — so forwarding None-valued keys makes an
            # unset optional param fail legacy validation. Drop them and let
            # the legacy tool apply its own defaults, exactly as it did before
            # this wrapper existed.
            filtered = {k: v for k, v in kwargs.items() if v is not None}
            return await tool.execute(**filtered)

        return cls(
            name=tool.get_name(),
            description=tool.get_description(),
            args_model=args_model,
            wire_schema=schema.parameters,
            handler=_handler,
            cacheable=cacheable,
            cache_ttl_s=cache_ttl_s,
            tags=tags,
        )

    def to_legacy_tool(self) -> Tool:
        """Adapt this ``ToolSpec`` back into a ``Tool`` — drop-in for the
        existing ``ToolExecutor``/tool-bundle pipeline, which still takes
        ``list[Tool]``."""
        return _ToolSpecAdapter(self)


class _ToolSpecAdapter(Tool):
    """``Tool`` view of a ``ToolSpec`` — see ``ToolSpec.to_legacy_tool``."""

    def __init__(self, spec: ToolSpec) -> None:
        self._spec = spec

    def get_schema(self) -> ToolSchema:
        return self._spec.to_tool_schema()

    def get_name(self) -> str:
        return self._spec.name

    def get_description(self) -> str:
        return self._spec.description

    def validate_parameters(self, **kwargs: Any) -> dict[str, Any]:
        validated = self._spec.args_model.model_validate(kwargs)
        return validated.model_dump()

    async def execute(self, **kwargs: Any) -> ToolResult[Any]:
        validated = self.validate_parameters(**kwargs)
        return await self._spec.handler(**validated)
