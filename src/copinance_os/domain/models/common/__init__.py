"""Shared DDD primitives and methodology envelopes."""

from copinance_os.domain.models.common.base import Entity, ValueObject
from copinance_os.domain.models.common.methodology import (
    ANALYSIS_METHODOLOGY_ENVELOPE_VERSION,
    AnalysisMethodology,
    MethodologyReference,
    MethodologySpec,
    analysis_methodology_single_spec,
    envelope_from_text_methodology,
)

__all__ = [
    "ANALYSIS_METHODOLOGY_ENVELOPE_VERSION",
    "Entity",
    "ValueObject",
    "AnalysisMethodology",
    "MethodologyReference",
    "MethodologySpec",
    "analysis_methodology_single_spec",
    "envelope_from_text_methodology",
]
