"""European vanilla option Greeks via QuantLib (analytic Black–Scholes–Merton).

First-order sensitivities use ``AnalyticEuropeanEngine``. Higher-order closed-form
pieces (vanna, charm, volga) use the same BSM ``d1``, ``d2`` as the engine inputs.

Research touchpoints (methodology / interpretation, not model assumptions here):

- **Vanna** (∂²V/∂S∂σ): smile-dynamics and spot–vol correlation hedging flows are
  standard in Bergomi, *Smile Dynamics IV* (2005).
- **Charm** (∂Δ/∂τ, calendar time): dealer delta drift with time; see Taleb,
  *Dynamic Hedging* (1997), esp. Ch.9.
- **Volga** (∂²V/∂σ²): wing convexity / vol-of-vol; variance-surface context in
  Carr & Wu, *Variance Risk Premiums* (2009).
- **NPV** vs market mid: systematic deviation from BSM at quoted IV as a sentiment
  read; De Fontnouvelle et al. (2003) on option mispricing.
- **P(ITM)** from ``itmCashProbability``: risk-neutral exercise probability;
  combined with OI for pin-style heuristics per Avellaneda & Lipkin (2003).
"""

from __future__ import annotations

import math
from datetime import date
from decimal import Decimal
from typing import Any

import structlog

from copinance_os.data.analytics.options.assumptions import (
    resolve_option_greek_assumptions,
)
from copinance_os.data.analytics.options.constants import DEFAULT_RISK_FREE_RATE
from copinance_os.domain.models.market import OptionContract, OptionGreeks, OptionsChain, OptionSide
from copinance_os.domain.models.profile import AnalysisProfile
from copinance_os.infra.config import get_settings

logger = structlog.get_logger(__name__)

try:
    import QuantLib
except ImportError:  # pragma: no cover
    QuantLib = None

_HIGHER_ORDER_GREEK_FIELDS = (
    "vanna",
    "charm",
    "volga",
    "theoretical_price",
    "itm_probability",
)


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _norm_cdf(x: float) -> float:
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def _compute_d1_d2(
    spot: float, strike: float, r: float, q: float, vol: float, t: float
) -> tuple[float, float]:
    sqrt_t = math.sqrt(t)
    d1 = (math.log(spot / strike) + (r - q + 0.5 * vol * vol) * t) / (vol * sqrt_t)
    d2 = d1 - vol * sqrt_t
    return d1, d2


def _greeks_missing_higher_order(g: OptionGreeks) -> bool:
    return any(getattr(g, name) is None for name in _HIGHER_ORDER_GREEK_FIELDS)


def _merge_higher_order_greeks(existing: OptionGreeks, fresh: OptionGreeks) -> OptionGreeks:
    data = existing.model_dump()
    for name in _HIGHER_ORDER_GREEK_FIELDS:
        if data.get(name) is None:
            val = getattr(fresh, name)
            if val is not None:
                data[name] = val
    return OptionGreeks(**data)


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
    """Return analytic BSM Greeks, or ``None`` when inputs are invalid or QuantLib is unavailable.

    See module docstring for literature tied to higher-order Greeks and NPV / P(ITM).
    """
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

        t_year = float(day_count.yearFraction(ql_eval, ql_maturity))
        theoretical_price = Decimal(str(option.NPV()))
        itm_probability = Decimal(str(option.itmCashProbability()))

        vanna: Decimal | None = None
        charm: Decimal | None = None
        volga: Decimal | None = None
        if t_year > 1e-10 and vol > 1e-12:
            d1, d2 = _compute_d1_d2(spot_f, strike_f, r, q, vol, t_year)
            vanna_f = -math.exp(-q * t_year) * _norm_pdf(d1) * d2 / vol
            sqrt_t = math.sqrt(t_year)
            charm_base = (
                -math.exp(-q * t_year)
                * _norm_pdf(d1)
                * (2.0 * (r - q) * t_year - d2 * vol * sqrt_t)
                / (2.0 * t_year * vol * sqrt_t)
            )
            if side is OptionSide.CALL:
                charm_f = charm_base - q * math.exp(-q * t_year) * _norm_cdf(d1)
            else:
                charm_f = charm_base + q * math.exp(-q * t_year) * _norm_cdf(-d1)
            vega_f = float(option.vega())
            volga_f = vega_f * d1 * d2 / vol
            vanna = Decimal(str(vanna_f))
            charm = Decimal(str(charm_f))
            volga = Decimal(str(volga_f))

        return OptionGreeks(
            delta=Decimal(str(option.delta())),
            gamma=Decimal(str(option.gamma())),
            theta=Decimal(str(option.theta())),
            vega=Decimal(str(option.vega())),
            rho=Decimal(str(option.rho())),
            vanna=vanna,
            charm=charm,
            volga=volga,
            theoretical_price=theoretical_price,
            itm_probability=itm_probability,
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
    only_missing: bool = False,
) -> tuple[OptionContract, bool]:
    if underlying_price is None or contract.implied_volatility is None:
        return contract, False
    fresh = compute_european_bsm_greeks(
        spot=underlying_price,
        strike=contract.strike,
        risk_free_rate=risk_free_rate,
        dividend_yield=dividend_yield,
        implied_volatility=contract.implied_volatility,
        expiration_date=contract.expiration_date,
        evaluation_date=evaluation_date,
        side=contract.side,
    )
    if fresh is None:
        return contract, False
    if only_missing and contract.greeks is not None:
        if not _greeks_missing_higher_order(contract.greeks):
            return contract, False
        merged = _merge_higher_order_greeks(contract.greeks, fresh)
        return contract.model_copy(update={"greeks": merged}), merged != contract.greeks
    return contract.model_copy(update={"greeks": fresh}), True


def estimate_bsm_greeks_for_options_chain(
    chain: OptionsChain,
    *,
    risk_free_rate: Decimal = DEFAULT_RISK_FREE_RATE,
    dividend_yield: Decimal = Decimal("0"),
    evaluation_date: date | None = None,
    only_missing: bool = False,
) -> OptionsChain:
    """Estimate European BSM Greeks per contract when spot and implied vol are available.

    If QuantLib is not installed or no estimate succeeds, ``chain`` is returned unchanged
    and chain metadata is not augmented with model provenance.

    When ``only_missing`` is True, rows without ``greeks`` are filled. Rows that already
    have vendor first-order Greeks are preserved, but missing higher-order fields
    (vanna, charm, volga, theoretical_price, itm_probability) are merged from the same
    QuantLib pass without overwriting delta/gamma/theta/vega/rho.
    """
    if QuantLib is None:
        return chain

    eval_d = evaluation_date or date.today()
    added = False
    calls_out: list[OptionContract] = []
    for c in chain.calls or []:
        if only_missing and c.greeks is not None and not _greeks_missing_higher_order(c.greeks):
            calls_out.append(c)
            continue
        new_c, changed = _estimate_greeks_on_contract(
            c,
            underlying_price=chain.underlying_price,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield,
            evaluation_date=eval_d,
            only_missing=only_missing,
        )
        if changed:
            added = True
        calls_out.append(new_c)

    puts_out: list[OptionContract] = []
    for c in chain.puts or []:
        if only_missing and c.greeks is not None and not _greeks_missing_higher_order(c.greeks):
            puts_out.append(c)
            continue
        new_c, changed = _estimate_greeks_on_contract(
            c,
            underlying_price=chain.underlying_price,
            risk_free_rate=risk_free_rate,
            dividend_yield=dividend_yield,
            evaluation_date=eval_d,
            only_missing=only_missing,
        )
        if changed:
            added = True
        puts_out.append(new_c)

    if only_missing and not added:
        return chain

    if not any(c.greeks for c in calls_out) and not any(c.greeks for c in puts_out):
        return chain

    meta = dict(chain.metadata)
    meta["option_greeks_model"] = "quantlib_analytic_european_bsm"
    meta["option_greeks_risk_free_rate"] = str(risk_free_rate)
    meta["option_greeks_dividend_yield_assumption"] = str(dividend_yield)
    meta["option_greeks_as_of_date"] = eval_d.isoformat()
    return chain.model_copy(update={"calls": calls_out, "puts": puts_out, "metadata": meta})


def enrich_options_chain_missing_greeks(
    chain: OptionsChain,
    *,
    evaluation_date: date | None = None,
    profile: AnalysisProfile | None = None,
) -> OptionsChain:
    """Fill missing Greeks via QuantLib analytic European BSM when spot/IV allow.

    Rows with ``greeks is None`` get a full estimate. Rows with vendor first-order Greeks
    but missing higher-order fields get a non-destructive merge from the same engine.

    Uses the same risk-free and dividend assumptions as :class:`QuantLibBsmGreekEstimator`.
    Returns ``chain`` unchanged when QuantLib is unavailable or no row is filled.
    """
    if QuantLib is None:
        return chain
    risk_free, div_default = resolve_option_greek_assumptions(
        settings=get_settings(),
        profile=profile,
    )
    div_yield = _effective_dividend_yield(chain, div_default)
    return estimate_bsm_greeks_for_options_chain(
        chain,
        risk_free_rate=risk_free,
        dividend_yield=div_yield,
        evaluation_date=evaluation_date,
        only_missing=True,
    )


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
