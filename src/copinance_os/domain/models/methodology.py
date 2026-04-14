"""Shared methodology envelope for analysis outputs (specs + data inputs)."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import ConfigDict, Field, field_serializer

from copinance_os.domain.models.base import ValueObject

ANALYSIS_METHODOLOGY_ENVELOPE_VERSION = "analysis_methodology_v1"


class MethodologyReference(ValueObject):
    """External citation for a methodology spec."""

    id: str
    title: str
    url: str


class MethodologySpec(ValueObject):
    """One algorithm / sub-computation with transparent parameters."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    version: str
    model_family: str
    assumptions: tuple[str, ...]
    limitations: tuple[str, ...]
    references: tuple[MethodologyReference, ...]
    parameters: dict[str, str] = Field(default_factory=dict)


class AnalysisMethodology(ValueObject):
    """Envelope attached to analysis-like results (positioning, reports, regime slices)."""

    model_config = ConfigDict(populate_by_name=True)

    version: str = Field(
        default=ANALYSIS_METHODOLOGY_ENVELOPE_VERSION,
        description="Envelope schema version",
    )
    computed_at: datetime
    specs: tuple[MethodologySpec, ...]
    data_inputs: dict[str, str] = Field(default_factory=dict)

    @field_serializer("computed_at")
    def _ser_computed_at(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat()


def analysis_methodology_single_spec(
    *,
    spec: MethodologySpec,
    data_inputs: dict[str, str],
    computed_at: datetime | None = None,
) -> AnalysisMethodology:
    """Build an envelope with exactly one spec (common for CLI / executor summaries)."""
    return AnalysisMethodology(
        computed_at=computed_at or datetime.now(UTC),
        specs=(spec,),
        data_inputs=dict(data_inputs),
    )


def envelope_from_text_methodology(
    *,
    spec_id: str,
    model_family: str,
    assumptions: tuple[str, ...],
    limitations: tuple[str, ...],
    data_inputs: dict[str, str],
    parameters: dict[str, str] | None = None,
    computed_at: datetime | None = None,
) -> AnalysisMethodology:
    """Single-spec envelope from plain-language methodology strings (reports, summaries)."""
    spec = MethodologySpec(
        id=spec_id,
        version="v1",
        model_family=model_family,
        assumptions=assumptions,
        limitations=limitations,
        references=(),
        parameters=dict(parameters or {}),
    )
    return analysis_methodology_single_spec(
        spec=spec, data_inputs=data_inputs, computed_at=computed_at
    )
