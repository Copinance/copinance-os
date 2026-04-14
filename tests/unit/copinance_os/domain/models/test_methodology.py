"""Tests for shared methodology value objects."""

from datetime import UTC, datetime

from copinance_os.domain.models.methodology import (
    AnalysisMethodology,
    MethodologyReference,
    MethodologySpec,
    analysis_methodology_single_spec,
)


def test_methodology_spec_roundtrip() -> None:
    ref = MethodologyReference(id="R1", title="T", url="https://example.com")
    spec = MethodologySpec(
        id="test.algo",
        version="v1",
        model_family="mf",
        assumptions=("a",),
        limitations=("l",),
        references=(ref,),
        parameters={"k": "v"},
    )
    d = spec.model_dump(mode="json")
    spec2 = MethodologySpec.model_validate(d)
    assert spec2 == spec
    assert spec2.references[0].url == "https://example.com"


def test_analysis_methodology_envelope() -> None:
    spec = MethodologySpec(
        id="x",
        version="v1",
        model_family="m",
        assumptions=(),
        limitations=(),
        references=(),
    )
    env = analysis_methodology_single_spec(
        spec=spec,
        data_inputs={"symbol": "SPY"},
        computed_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
    )
    assert isinstance(env, AnalysisMethodology)
    assert env.version == "analysis_methodology_v1"
    assert env.specs == (spec,)
