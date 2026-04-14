"""Methodology envelope for QuantLib European BSM per-contract Greeks."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from copinance_os.domain.models.methodology import (
    ANALYSIS_METHODOLOGY_ENVELOPE_VERSION,
    AnalysisMethodology,
    MethodologyReference,
    MethodologySpec,
)

_REF_QUANTLIB = MethodologyReference(
    id="REF_QUANTLIB_ANALYTIC_EUROPEAN",
    title="QuantLib AnalyticEuropeanEngine",
    url="https://www.quantlib.org/",
)
_REF_BERGOMI = MethodologyReference(
    id="REF_BERGOMI_2005",
    title="Lorenzo Bergomi (2005), Smile Dynamics IV",
    url="https://www.risk.net/derivatives/equity-derivatives/1510166/smile-dynamics",
)
_REF_TALEB = MethodologyReference(
    id="REF_TALEB_1997",
    title="Nassim Nicholas Taleb (1997), Dynamic Hedging",
    url="https://onlinelibrary.wiley.com/doi/book/10.1002/9781119198665",
)
_REF_CARR_WU = MethodologyReference(
    id="REF_CARR_WU_2009",
    title="Carr and Wu (2009), Variance Risk Premiums",
    url="https://doi.org/10.1093/rfs/hhp063",
)


def quantlib_bsm_greeks_methodology(
    *,
    risk_free_rate: Decimal,
    dividend_yield: Decimal,
    evaluation_date: date,
    computed_at: datetime | None = None,
) -> AnalysisMethodology:
    """Single-spec envelope describing the analytic European BSM Greek pass."""
    spec = MethodologySpec(
        id="options.greeks.quantlib_bsm_european",
        version="v1",
        model_family="quantlib_analytic_european_bsm",
        assumptions=(
            "European exercise; Black-Scholes-Merton dynamics; "
            "flat risk-free and dividend curves; constant implied volatility per contract.",
        ),
        limitations=(
            "American exercise, discrete dividends, and smile dynamics are not modeled in-engine.",
        ),
        references=(_REF_QUANTLIB, _REF_BERGOMI, _REF_TALEB, _REF_CARR_WU),
        parameters={
            "risk_free_rate": str(risk_free_rate),
            "dividend_yield": str(dividend_yield),
            "evaluation_date": evaluation_date.isoformat(),
        },
    )
    return AnalysisMethodology(
        version=ANALYSIS_METHODOLOGY_ENVELOPE_VERSION,
        computed_at=computed_at or datetime.now(UTC),
        specs=(spec,),
        data_inputs={"evaluation_date": evaluation_date.isoformat()},
    )
