"""Positioning methodology envelope assembly for component-distributed outputs."""

from __future__ import annotations

from datetime import UTC, date, datetime

from copinance_os.domain.models.common.methodology import (
    ANALYSIS_METHODOLOGY_ENVELOPE_VERSION,
    AnalysisMethodology,
    MethodologySpec,
)


def build_cross_cutting_positioning_specs(
    *,
    component_specs: dict[str, MethodologySpec],
    greeks_specs: tuple[MethodologySpec, ...] | None,
) -> tuple[MethodologySpec, ...]:
    base_specs = (
        component_specs["data_quality"],
        component_specs["bias"],
    )
    if greeks_specs:
        return (*greeks_specs, *base_specs)
    return base_specs


def build_positioning_analysis_methodology(
    *,
    specs: tuple[MethodologySpec, ...],
    symbol: str,
    window: str,
    ref_date: date,
    literacy: str,
    nearest_exp: str | None,
    second_exp: str | None,
    data_quality: float,
    enrich_greeks: bool,
    computed_at: datetime | None = None,
) -> AnalysisMethodology:
    def _exp(x: str | None) -> str:
        return x if x else "none"

    expiries = ",".join(x for x in (_exp(nearest_exp), _exp(second_exp)) if x != "none") or "none"
    return AnalysisMethodology(
        version=ANALYSIS_METHODOLOGY_ENVELOPE_VERSION,
        computed_at=computed_at or datetime.now(UTC),
        specs=specs,
        data_inputs={
            "symbol": symbol,
            "as_of_date": ref_date.isoformat(),
            "window": window,
            "financial_literacy": literacy,
            "expirations_used": expiries,
            "data_quality": f"{data_quality:.4f}",
            "enrich_missing_greeks": str(enrich_greeks),
        },
    )
