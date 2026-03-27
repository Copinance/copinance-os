"""European vanilla option Greeks via QuantLib (analytic Black–Scholes–Merton)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import structlog

from copinanceos.domain.models.market import OptionContract, OptionGreeks, OptionsChain, OptionSide
from copinanceos.domain.models.profile import AnalysisProfile
from copinanceos.infrastructure.analytics.options.assumptions import (
    resolve_option_greek_assumptions,
)
from copinanceos.infrastructure.analytics.options.constants import DEFAULT_RISK_FREE_RATE
from copinanceos.infrastructure.config import get_settings

logger = structlog.get_logger(__name__)

try:
    import QuantLib
except ImportError:  # pragma: no cover
    QuantLib = None


def _chain_dividend_yield(chain: OptionsChain) -> Decimal | None:
    raw = chain.metadata.get("dividend_yield")
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return Decimal(str(raw))
    except Exception:
        return None


def _effective_dividend_yield(chain: OptionsChain, div_default: Decimal) -> Decimal:
    parsed = _chain_dividend_yield(chain)
    return parsed if parsed is not None else div_default


def _to_ql_date(d: date) -> Any:
    assert QuantLib is not None
    return QuantLib.Date(int(d.day), int(d.month), int(d.year))


def _ql_business_eval_date(evaluation_date: date) -> Any:
    assert QuantLib is not None
    calendar = QuantLib.UnitedStates(QuantLib.UnitedStates.NYSE)
    qd = _to_ql_date(evaluation_date)
    if calendar.isBusinessDay(qd):
        return qd
    return calendar.adjust(qd, QuantLib.Following)


def compute_european_bsm_greeks(
    *,
    spot: Decimal,
    strike: Decimal,
    risk_free_rate: Decimal,
    dividend_yield: Decimal,
    implied_volatility: Decimal,
    expiration_date: date,
    evaluation_date: date,
    side: OptionSide,
) -> OptionGreeks | None:
    """Return analytic BSM Greeks, or ``None`` when inputs are invalid or QuantLib is unavailable."""
    if QuantLib is None:
        logger.warning("quantlib_not_available", message="QuantLib is not installed")
        return None
    if side not in (OptionSide.CALL, OptionSide.PUT):
        return None
    if spot <= 0 or strike <= 0 or implied_volatility <= 0:
        return None

    try:
        ql_eval = _ql_business_eval_date(evaluation_date)
        ql_maturity = _to_ql_date(expiration_date)
        # Strictly past expiry: no BSM Greeks. Same calendar day as eval may be 0DTE; allow.
        if ql_maturity < ql_eval:
            return None

        QuantLib.Settings.instance().evaluationDate = ql_eval

        spot_f = float(spot)
        strike_f = float(strike)
        r = float(risk_free_rate)
        q = float(dividend_yield)
        vol = float(implied_volatility)

        option_type = QuantLib.Option.Call if side is OptionSide.CALL else QuantLib.Option.Put
        payoff = QuantLib.PlainVanillaPayoff(option_type, strike_f)
        exercise = QuantLib.EuropeanExercise(ql_maturity)
        option = QuantLib.EuropeanOption(payoff, exercise)

        day_count = QuantLib.Actual365Fixed()
        calendar = QuantLib.UnitedStates(QuantLib.UnitedStates.NYSE)

        spot_handle = QuantLib.QuoteHandle(QuantLib.SimpleQuote(spot_f))
        rf_handle = QuantLib.YieldTermStructureHandle(QuantLib.FlatForward(ql_eval, r, day_count))
        div_handle = QuantLib.YieldTermStructureHandle(QuantLib.FlatForward(ql_eval, q, day_count))
        vol_handle = QuantLib.BlackVolTermStructureHandle(
            QuantLib.BlackConstantVol(ql_eval, calendar, vol, day_count)
        )

        process = QuantLib.BlackScholesMertonProcess(spot_handle, div_handle, rf_handle, vol_handle)
        engine = QuantLib.AnalyticEuropeanEngine(process)
        option.setPricingEngine(engine)

        return OptionGreeks(
            delta=Decimal(str(option.delta())),
            gamma=Decimal(str(option.gamma())),
            theta=Decimal(str(option.theta())),
            vega=Decimal(str(option.vega())),
            rho=Decimal(str(option.rho())),
        )
    except Exception as e:
        logger.debug("quantlib_greeks_failed", error=str(e))
        return None


def _estimate_greeks_on_contract(
    contract: OptionContract,
    *,
    underlying_price: Decimal | None,
    risk_free_rate: Decimal,
    dividend_yield: Decimal,
    evaluation_date: date,
) -> OptionContract:
    if underlying_price is None or contract.implied_volatility is None:
        return contract
    greeks = compute_european_bsm_greeks(
        spot=underlying_price,
        strike=contract.strike,
        risk_free_rate=risk_free_rate,
        dividend_yield=dividend_yield,
        implied_volatility=contract.implied_volatility,
        expiration_date=contract.expiration_date,
        evaluation_date=evaluation_date,
        side=contract.side,
    )
    if greeks is None:
        return contract
    return contract.model_copy(update={"greeks": greeks})


def estimate_bsm_greeks_for_options_chain(
    chain: OptionsChain,
    *,
    risk_free_rate: Decimal = DEFAULT_RISK_FREE_RATE,
    dividend_yield: Decimal = Decimal("0"),
    evaluation_date: date | None = None,
) -> OptionsChain:
    """Estimate European BSM Greeks per contract when spot and implied vol are available.

    If QuantLib is not installed or no estimate succeeds, ``chain`` is returned unchanged
    and chain metadata is not augmented with model provenance.
    """
    if QuantLib is None:
        return chain

    eval_d = evaluation_date or date.today()
    calls = [
        _estimate_greeks_on_contract(
            c,
            underlying_price=chain.underlying_price,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield,
            evaluation_date=eval_d,
        )
        for c in chain.calls
    ]
    puts = [
        _estimate_greeks_on_contract(
            c,
            underlying_price=chain.underlying_price,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield,
            evaluation_date=eval_d,
        )
        for c in chain.puts
    ]
    if not any(c.greeks for c in calls) and not any(c.greeks for c in puts):
        return chain

    meta = dict(chain.metadata)
    meta["option_greeks_model"] = "quantlib_analytic_european_bsm"
    meta["option_greeks_risk_free_rate"] = str(risk_free_rate)
    meta["option_greeks_dividend_yield_assumption"] = str(dividend_yield)
    meta["option_greeks_as_of_date"] = eval_d.isoformat()
    return chain.model_copy(update={"calls": calls, "puts": puts, "metadata": meta})


class QuantLibBsmGreekEstimator:
    """QuantLib-backed ``OptionsChainGreeksEstimator`` (analytic European BSM).

    Uses :func:`resolve_option_greek_assumptions` with :func:`get_settings` on each
    ``estimate`` call so environment changes are respected. Optional ``profile`` applies
    ``AnalysisProfile.preferences`` overrides (for custom DI wiring); the default
    container leaves this unset.
    """

    def __init__(self, profile: AnalysisProfile | None = None) -> None:
        self._profile = profile

    def estimate(self, chain: OptionsChain) -> OptionsChain:
        risk_free, div_default = resolve_option_greek_assumptions(
            settings=get_settings(),
            profile=self._profile,
        )
        div_yield = _effective_dividend_yield(chain, div_default)
        return estimate_bsm_greeks_for_options_chain(
            chain,
            risk_free_rate=risk_free,
            dividend_yield=div_yield,
            evaluation_date=date.today(),
        )
