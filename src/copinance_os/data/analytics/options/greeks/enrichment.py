"""High-level chain enrichment using profile-driven BSM assumptions."""

from __future__ import annotations

from datetime import date

from typing_extensions import override

from copinance_os.data.analytics.options.greeks.config import resolve_option_greek_assumptions
from copinance_os.data.analytics.options.greeks.engine import (
    chain_effective_dividend_yield,
    estimate_bsm_greeks_for_options_chain,
)
from copinance_os.domain.models.market import OptionsChain
from copinance_os.domain.models.profile import AnalysisProfile
from copinance_os.domain.ports.analytics import OptionsChainGreeksEstimator
from copinance_os.infra.config import get_settings

try:
    import QuantLib
except ImportError:  # pragma: no cover
    QuantLib = None


def enrich_options_chain_missing_greeks(
    chain: OptionsChain,
    *,
    evaluation_date: date | None = None,
    profile: AnalysisProfile | None = None,
) -> OptionsChain:
    """Fill missing Greeks via QuantLib analytic European BSM when spot/IV allow."""
    if QuantLib is None:
        return chain
    risk_free, div_default = resolve_option_greek_assumptions(
        settings=get_settings(),
        profile=profile,
    )
    div_yield = chain_effective_dividend_yield(chain, div_default)
    return estimate_bsm_greeks_for_options_chain(
        chain,
        risk_free_rate=risk_free,
        dividend_yield=div_yield,
        evaluation_date=evaluation_date,
        only_missing=True,
    )


class QuantLibBsmGreekEstimator(OptionsChainGreeksEstimator):
    """QuantLib-backed ``OptionsChainGreeksEstimator`` (analytic European BSM)."""

    def __init__(self, profile: AnalysisProfile | None = None) -> None:
        self._profile = profile

    @override
    def estimate(self, chain: OptionsChain) -> OptionsChain:
        risk_free, div_default = resolve_option_greek_assumptions(
            settings=get_settings(),
            profile=self._profile,
        )
        div_yield = chain_effective_dividend_yield(chain, div_default)
        return estimate_bsm_greeks_for_options_chain(
            chain,
            risk_free_rate=risk_free,
            dividend_yield=div_yield,
            evaluation_date=date.today(),
        )
