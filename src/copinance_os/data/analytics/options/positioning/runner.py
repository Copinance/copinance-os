"""Public entry points for aggregate options positioning."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from copinance_os.data.analytics.options.greeks.enrichment import (
    enrich_options_chain_missing_greeks,
)
from copinance_os.data.analytics.options.positioning.compose import (
    compose_options_positioning_payload,
)
from copinance_os.data.analytics.options.positioning.config import (
    DEFAULT_POSITIONING_METHODOLOGY,
    PositioningMethodology,
)
from copinance_os.data.analytics.options.positioning.contracts import (
    nearest_expirations,
    sorted_expirations,
)
from copinance_os.data.analytics.options.positioning.methodology import (
    build_positioning_analysis_methodology,
    merge_positioning_methodology_specs,
)
from copinance_os.domain.literacy import resolve_financial_literacy
from copinance_os.domain.models.market import OptionContract, OptionsChain
from copinance_os.domain.models.options_positioning import OptionsPositioningResult
from copinance_os.domain.models.profile import AnalysisProfile, FinancialLiteracy
from copinance_os.domain.ports.data_providers import MarketDataProvider


def build_options_positioning(
    *,
    chain: OptionsChain,
    calls: list[OptionContract],
    puts: list[OptionContract],
    quote: dict[str, Any],
    symbol: str,
    window: Literal["near", "mid"],
    financial_literacy: FinancialLiteracy | str | None = None,
    as_of_date: date | None = None,
    enrich_missing_greeks: bool = False,
    analysis_profile: AnalysisProfile | None = None,
    methodology: PositioningMethodology = DEFAULT_POSITIONING_METHODOLOGY,
) -> OptionsPositioningResult:
    """Compute aggregate positioning; returns a validated :class:`OptionsPositioningResult`."""
    lit = resolve_financial_literacy(financial_literacy)
    ref_date = as_of_date or date.today()
    chain_work = chain
    calls_work = calls
    puts_work = puts
    if enrich_missing_greeks:
        merged = chain.model_copy(update={"calls": calls, "puts": puts})
        merged = enrich_options_chain_missing_greeks(
            merged, evaluation_date=ref_date, profile=analysis_profile
        )
        chain_work = merged
        calls_work = list(chain_work.calls or [])
        puts_work = list(chain_work.puts or [])

    payload = compose_options_positioning_payload(
        chain=chain_work,
        calls=calls_work,
        puts=puts_work,
        quote=quote,
        symbol=symbol,
        window=window,
        lit=lit,
        ref_date=ref_date,
        methodology=methodology,
    )

    sorted_exp = sorted_expirations(chain_work, calls_work, puts_work)
    near_exps = nearest_expirations(sorted_exp, 2)
    nearest_exp = near_exps[0] if near_exps else None
    second_exp = near_exps[1] if len(near_exps) > 1 else None

    dq = float(payload["data_quality"] or 0.0)
    greek_specs = chain_work.greeks_methodology.specs if chain_work.greeks_methodology else None
    merged_specs = merge_positioning_methodology_specs(methodology.specs(), greek_specs)
    envelope = build_positioning_analysis_methodology(
        specs=merged_specs,
        symbol=symbol,
        window=window,
        ref_date=ref_date,
        literacy=lit.value,
        nearest_exp=nearest_exp,
        second_exp=second_exp,
        data_quality=dq,
        enrich_greeks=enrich_missing_greeks,
    )
    return OptionsPositioningResult.model_validate({**payload, "methodology": envelope})


async def compute_options_positioning_context(
    provider: MarketDataProvider,
    symbol: str,
    window: Literal["near", "mid"] = "near",
    financial_literacy: FinancialLiteracy | str | None = None,
) -> OptionsPositioningResult:
    """Fetch quote + full chain and compute aggregate options-intelligence metrics."""
    sym = symbol.strip().upper()
    quote = await provider.get_quote(sym) or {}
    chain = await provider.get_options_chain(underlying_symbol=sym, expiration_date=None)
    calls = list(chain.calls or [])
    puts = list(chain.puts or [])
    return build_options_positioning(
        chain=chain,
        calls=calls,
        puts=puts,
        quote=quote,
        symbol=sym,
        window=window,
        financial_literacy=financial_literacy,
        enrich_missing_greeks=True,
    )
