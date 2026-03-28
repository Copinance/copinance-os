"""Declarative plugin identifiers for config-driven registration."""

from typing import Literal

from pydantic import BaseModel, Field


class PluginSpec(BaseModel):
    """Static description of a pluggable component (resolved at runtime via import path)."""

    name: str = Field(..., min_length=1, description="Unique registry key")
    kind: Literal["indicator", "strategy", "tool"] = Field(
        ...,
        description="Plugin category for routing and validation",
    )
    import_path: str = Field(
        ...,
        description="Dotted module path (e.g. copinance_os.domain.indicators)",
    )
    qualified_name: str = Field(
        ...,
        description="Attribute name on the module (class or callable)",
    )
