"""Methodology envelope for QuantLib European BSM per-contract Greeks."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from copinance_os.domain.models.common.methodology import (
    ANALYSIS_METHODOLOGY_ENVELOPE_VERSION,
    AnalysisMethodology,
    MethodologyReference,
    MethodologySpec,
)

_REF_QUANTLIB = MethodologyReference(
    id="REF_QUANTLIB_ANALYTIC_EUROPEAN",
    title="QuantLib Development Group (2021), AnalyticEuropeanEngine (ql/pricingengines/vanilla/analyticeuropeanengine.hpp)",
    url="https://github.com/lballabio/QuantLib/blob/master/ql/pricingengines/vanilla/analyticeuropeanengine.hpp",
)
_REF_BERGOMI = MethodologyReference(
    id="REF_BERGOMI_2005",
    title="Bergomi, L. (2005), Smile dynamics IV (Risk.net technical paper)",
    url="https://www.risk.net/derivatives/equity-derivatives/1510166/smile-dynamics",
)
_REF_TALEB = MethodologyReference(
    id="REF_TALEB_1997",
    title="Taleb, N. N. (1997), Dynamic hedging: Managing vanilla and exotic options (John Wiley & Sons; ISBN 978-0-471-15280-4)",
    url="https://www.wiley.com/en-us/Dynamic+Hedging%3A+Managing+Vanilla+and+Exotic+Options-p-9780471152804",
)
_REF_CARR_WU = MethodologyReference(
    id="REF_CARR_WU_2009",
    title="Carr, P., & Wu, L. (2009), Variance risk premiums, The Review of Financial Studies, 22(3), 1311-1341",
    url="https://doi.org/10.1093/rfs/hhn038",
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
