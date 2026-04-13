"""Tests for QuantLib-backed Black–Scholes–Merton Greeks."""

import math
from datetime import date
from decimal import Decimal

import pytest

pytest.importorskip("QuantLib")

from copinance_os.data.analytics.options.quantlib_bsm_greeks import (
    QuantLibBsmGreekEstimator,
    compute_european_bsm_greeks,
    enrich_options_chain_missing_greeks,
    estimate_bsm_greeks_for_options_chain,
)
from copinance_os.domain.models.market import OptionContract, OptionGreeks, OptionsChain, OptionSide
from copinance_os.infra.config import Settings


@pytest.mark.unit
def test_compute_atm_call_delta_in_reasonable_range() -> None:
    greeks = compute_european_bsm_greeks(
        spot=Decimal("100"),
        strike=Decimal("100"),
        risk_free_rate=Decimal("0.05"),
        dividend_yield=Decimal("0"),
        implied_volatility=Decimal("0.20"),
        expiration_date=date(2027, 3, 28),
        evaluation_date=date(2026, 3, 28),
        side=OptionSide.CALL,
    )
    assert greeks is not None
    assert Decimal("0.40") < greeks.delta < Decimal("0.65")


@pytest.mark.unit
def test_compute_returns_none_when_strictly_expired() -> None:
    assert (
        compute_european_bsm_greeks(
            spot=Decimal("100"),
            strike=Decimal("100"),
            risk_free_rate=Decimal("0.05"),
            dividend_yield=Decimal("0"),
            implied_volatility=Decimal("0.20"),
            expiration_date=date(2026, 3, 1),
            evaluation_date=date(2026, 3, 28),
            side=OptionSide.CALL,
        )
        is None
    )


@pytest.mark.unit
def test_compute_same_calendar_day_as_eval_not_rejected() -> None:
    """Regression: expiry on the evaluation calendar day is allowed (not ``< ql_eval``)."""
    greeks = compute_european_bsm_greeks(
        spot=Decimal("100"),
        strike=Decimal("100"),
        risk_free_rate=Decimal("0.05"),
        dividend_yield=Decimal("0"),
        implied_volatility=Decimal("0.25"),
        expiration_date=date(2026, 3, 27),
        evaluation_date=date(2026, 3, 27),
        side=OptionSide.CALL,
    )
    assert greeks is not None


@pytest.mark.unit
def test_compute_one_day_to_expiry_atm_call_delta_in_reasonable_range() -> None:
    greeks = compute_european_bsm_greeks(
        spot=Decimal("100"),
        strike=Decimal("100"),
        risk_free_rate=Decimal("0.05"),
        dividend_yield=Decimal("0"),
        implied_volatility=Decimal("0.25"),
        expiration_date=date(2026, 3, 28),
        evaluation_date=date(2026, 3, 27),
        side=OptionSide.CALL,
    )
    assert greeks is not None
    assert Decimal("0.35") < greeks.delta < Decimal("0.65")


@pytest.mark.unit
def test_compute_returns_none_for_nonpositive_spot_or_strike() -> None:
    assert (
        compute_european_bsm_greeks(
            spot=Decimal("0"),
            strike=Decimal("100"),
            risk_free_rate=Decimal("0.05"),
            dividend_yield=Decimal("0"),
            implied_volatility=Decimal("0.20"),
            expiration_date=date(2027, 3, 28),
            evaluation_date=date(2026, 3, 28),
            side=OptionSide.CALL,
        )
        is None
    )
    assert (
        compute_european_bsm_greeks(
            spot=Decimal("100"),
            strike=Decimal("-1"),
            risk_free_rate=Decimal("0.05"),
            dividend_yield=Decimal("0"),
            implied_volatility=Decimal("0.20"),
            expiration_date=date(2027, 3, 28),
            evaluation_date=date(2026, 3, 28),
            side=OptionSide.CALL,
        )
        is None
    )


@pytest.mark.unit
def test_compute_returns_none_for_invalid_side() -> None:
    assert (
        compute_european_bsm_greeks(
            spot=Decimal("100"),
            strike=Decimal("100"),
            risk_free_rate=Decimal("0.05"),
            dividend_yield=Decimal("0"),
            implied_volatility=Decimal("0.20"),
            expiration_date=date(2027, 3, 28),
            evaluation_date=date(2026, 3, 28),
            side=OptionSide.ALL,
        )
        is None
    )


@pytest.mark.unit
def test_compute_atm_put_delta_negative() -> None:
    greeks = compute_european_bsm_greeks(
        spot=Decimal("100"),
        strike=Decimal("100"),
        risk_free_rate=Decimal("0.05"),
        dividend_yield=Decimal("0"),
        implied_volatility=Decimal("0.20"),
        expiration_date=date(2027, 3, 28),
        evaluation_date=date(2026, 3, 28),
        side=OptionSide.PUT,
    )
    assert greeks is not None
    assert Decimal("-0.65") < greeks.delta < Decimal("-0.35")


@pytest.mark.unit
def test_compute_returns_none_without_vol() -> None:
    assert (
        compute_european_bsm_greeks(
            spot=Decimal("100"),
            strike=Decimal("100"),
            risk_free_rate=Decimal("0.05"),
            dividend_yield=Decimal("0"),
            implied_volatility=Decimal("0"),
            expiration_date=date(2027, 3, 28),
            evaluation_date=date(2026, 3, 28),
            side=OptionSide.CALL,
        )
        is None
    )


@pytest.mark.unit
def test_estimate_chain_sets_greeks_and_metadata() -> None:
    chain = OptionsChain(
        underlying_symbol="SPY",
        expiration_date=date(2027, 3, 28),
        underlying_price=Decimal("400"),
        calls=[
            OptionContract(
                underlying_symbol="SPY",
                contract_symbol="SPY270328C00400000",
                side=OptionSide.CALL,
                strike=Decimal("400"),
                expiration_date=date(2027, 3, 28),
                implied_volatility=Decimal("0.18"),
            )
        ],
        puts=[
            OptionContract(
                underlying_symbol="SPY",
                contract_symbol="SPY270328P00400000",
                side=OptionSide.PUT,
                strike=Decimal("400"),
                expiration_date=date(2027, 3, 28),
                implied_volatility=Decimal("0.18"),
            )
        ],
    )
    out = estimate_bsm_greeks_for_options_chain(
        chain,
        risk_free_rate=Decimal("0.05"),
        dividend_yield=Decimal("0.01"),
        evaluation_date=date(2026, 3, 28),
    )
    assert out.calls[0].greeks is not None
    assert out.puts[0].greeks is not None
    assert out.metadata.get("option_greeks_model") == "quantlib_analytic_european_bsm"
    assert out.metadata.get("option_greeks_risk_free_rate") == "0.05"


@pytest.mark.unit
def test_estimate_chain_only_missing_returns_original_when_all_have_greeks() -> None:
    g = OptionGreeks(
        delta=Decimal("0.99"),
        gamma=Decimal("0.01"),
        theta=Decimal("0"),
        vega=Decimal("0"),
        rho=Decimal("0"),
        vanna=Decimal("0"),
        charm=Decimal("0"),
        volga=Decimal("0"),
        theoretical_price=Decimal("1"),
        itm_probability=Decimal("0.5"),
    )
    chain = OptionsChain(
        underlying_symbol="SPY",
        expiration_date=date(2027, 3, 28),
        underlying_price=Decimal("400"),
        calls=[
            OptionContract(
                underlying_symbol="SPY",
                contract_symbol="SPY270328C00400000",
                side=OptionSide.CALL,
                strike=Decimal("400"),
                expiration_date=date(2027, 3, 28),
                implied_volatility=Decimal("0.18"),
                greeks=g,
            )
        ],
        puts=[],
        metadata={"keep": "me"},
    )
    out = estimate_bsm_greeks_for_options_chain(
        chain,
        risk_free_rate=Decimal("0.05"),
        evaluation_date=date(2026, 3, 28),
        only_missing=True,
    )
    assert out is chain
    assert out.calls[0].greeks is not None
    assert out.calls[0].greeks.delta == Decimal("0.99")


@pytest.mark.unit
def test_estimate_chain_only_missing_fills_rows_without_greeks() -> None:
    vendor = OptionGreeks(
        delta=Decimal("0.11"),
        gamma=Decimal("0.02"),
        theta=Decimal("0"),
        vega=Decimal("0"),
        rho=Decimal("0"),
    )
    chain = OptionsChain(
        underlying_symbol="SPY",
        expiration_date=date(2027, 3, 28),
        underlying_price=Decimal("400"),
        calls=[
            OptionContract(
                underlying_symbol="SPY",
                contract_symbol="SPY270328C00400000",
                side=OptionSide.CALL,
                strike=Decimal("400"),
                expiration_date=date(2027, 3, 28),
                implied_volatility=Decimal("0.18"),
                greeks=vendor,
            ),
            OptionContract(
                underlying_symbol="SPY",
                contract_symbol="SPY270328C00410000",
                side=OptionSide.CALL,
                strike=Decimal("410"),
                expiration_date=date(2027, 3, 28),
                implied_volatility=Decimal("0.18"),
                greeks=None,
            ),
        ],
        puts=[],
    )
    out = estimate_bsm_greeks_for_options_chain(
        chain,
        risk_free_rate=Decimal("0.05"),
        dividend_yield=Decimal("0"),
        evaluation_date=date(2026, 3, 28),
        only_missing=True,
    )
    assert out is not chain
    assert out.calls[0].greeks is not None
    assert out.calls[0].greeks.delta == Decimal("0.11")
    assert out.calls[1].greeks is not None
    assert out.calls[1].greeks.delta != Decimal("0.11")


@pytest.mark.unit
def test_enrich_options_chain_missing_greeks_fills_when_quantlib_available() -> None:
    chain = OptionsChain(
        underlying_symbol="SPY",
        expiration_date=date(2027, 3, 28),
        underlying_price=Decimal("400"),
        calls=[
            OptionContract(
                underlying_symbol="SPY",
                contract_symbol="SPY270328C00400000",
                side=OptionSide.CALL,
                strike=Decimal("400"),
                expiration_date=date(2027, 3, 28),
                implied_volatility=Decimal("0.18"),
            )
        ],
        puts=[],
    )
    out = enrich_options_chain_missing_greeks(chain, evaluation_date=date(2026, 3, 28))
    assert out.calls[0].greeks is not None
    assert out.metadata.get("option_greeks_model") == "quantlib_analytic_european_bsm"


@pytest.mark.unit
def test_estimate_chain_unchanged_when_no_implied_vol() -> None:
    chain = OptionsChain(
        underlying_symbol="SPY",
        expiration_date=date(2027, 3, 28),
        underlying_price=Decimal("400"),
        calls=[
            OptionContract(
                underlying_symbol="SPY",
                contract_symbol="SPY270328C00400000",
                side=OptionSide.CALL,
                strike=Decimal("400"),
                expiration_date=date(2027, 3, 28),
                implied_volatility=None,
            )
        ],
        puts=[],
        metadata={"provider": "test"},
    )
    out = estimate_bsm_greeks_for_options_chain(chain, evaluation_date=date(2026, 3, 28))
    assert out is chain


@pytest.mark.unit
def test_estimate_chain_returns_original_when_no_underlying_price() -> None:
    chain = OptionsChain(
        underlying_symbol="SPY",
        expiration_date=date(2027, 3, 28),
        underlying_price=None,
        calls=[
            OptionContract(
                underlying_symbol="SPY",
                contract_symbol="SPY270328C00400000",
                side=OptionSide.CALL,
                strike=Decimal("400"),
                expiration_date=date(2027, 3, 28),
                implied_volatility=Decimal("0.18"),
            )
        ],
        puts=[],
    )
    out = estimate_bsm_greeks_for_options_chain(chain, evaluation_date=date(2026, 3, 28))
    assert out is chain


@pytest.mark.unit
def test_estimator_lowers_call_delta_when_chain_metadata_dividend_higher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``QuantLibBsmGreekEstimator`` uses chain ``metadata['dividend_yield']`` when set."""
    monkeypatch.setattr(
        "copinance_os.data.analytics.options.quantlib_bsm_greeks.get_settings",
        lambda: Settings(
            option_greeks_risk_free_rate=0.05,
            option_greeks_dividend_yield_default=0.0,
        ),
    )
    base = OptionsChain(
        underlying_symbol="SPY",
        expiration_date=date(2027, 3, 28),
        underlying_price=Decimal("400"),
        calls=[
            OptionContract(
                underlying_symbol="SPY",
                contract_symbol="SPY270328C00400000",
                side=OptionSide.CALL,
                strike=Decimal("400"),
                expiration_date=date(2027, 3, 28),
                implied_volatility=Decimal("0.18"),
            )
        ],
        puts=[],
    )
    low_div = QuantLibBsmGreekEstimator().estimate(base)
    high_div = QuantLibBsmGreekEstimator().estimate(
        base.model_copy(update={"metadata": {"dividend_yield": "0.06"}})
    )
    assert low_div.calls[0].greeks is not None
    assert high_div.calls[0].greeks is not None
    assert low_div.calls[0].greeks.delta > high_div.calls[0].greeks.delta


@pytest.mark.unit
def test_estimate_chain_only_missing_merges_higher_order_when_vendor_greeks_present() -> None:
    vendor = OptionGreeks(
        delta=Decimal("0.55"),
        gamma=Decimal("0.02"),
        theta=Decimal("-0.01"),
        vega=Decimal("0.03"),
        rho=Decimal("0.01"),
    )
    chain = OptionsChain(
        underlying_symbol="SPY",
        expiration_date=date(2027, 3, 28),
        underlying_price=Decimal("400"),
        calls=[
            OptionContract(
                underlying_symbol="SPY",
                contract_symbol="SPY270328C00400000",
                side=OptionSide.CALL,
                strike=Decimal("400"),
                expiration_date=date(2027, 3, 28),
                implied_volatility=Decimal("0.18"),
                greeks=vendor,
            ),
        ],
        puts=[],
    )
    out = estimate_bsm_greeks_for_options_chain(
        chain,
        risk_free_rate=Decimal("0.05"),
        dividend_yield=Decimal("0"),
        evaluation_date=date(2026, 3, 28),
        only_missing=True,
    )
    assert out is not chain
    g = out.calls[0].greeks
    assert g is not None
    assert g.delta == vendor.delta
    assert g.vanna is not None
    assert g.theoretical_price is not None
    assert g.itm_probability is not None


@pytest.mark.unit
def test_vanna_atm_call_sign() -> None:
    """ATM-forward strike (d2≈0) → vanna≈0; modestly ITM call vanna negative (1Y horizon)."""
    s = Decimal("100")
    r, q = Decimal("0.05"), Decimal("0")
    vol = Decimal("0.20")
    eval_d = date(2026, 6, 1)
    exp_d = date(2027, 6, 1)
    t = 1.0

    strike_atm = Decimal(str(100.0 * math.exp((float(r) - float(q) - 0.5 * float(vol) ** 2) * t)))
    g_atm = compute_european_bsm_greeks(
        spot=s,
        strike=strike_atm,
        risk_free_rate=r,
        dividend_yield=q,
        implied_volatility=vol,
        expiration_date=exp_d,
        evaluation_date=eval_d,
        side=OptionSide.CALL,
    )
    assert g_atm is not None and g_atm.vanna is not None
    assert abs(float(g_atm.vanna)) < 0.02
    g_itm = compute_european_bsm_greeks(
        spot=s,
        strike=Decimal("88"),
        risk_free_rate=r,
        dividend_yield=q,
        implied_volatility=vol,
        expiration_date=exp_d,
        evaluation_date=eval_d,
        side=OptionSide.CALL,
    )
    assert g_itm is not None and g_itm.vanna is not None
    assert float(g_itm.vanna) < 0


@pytest.mark.unit
def test_charm_positive_for_short_dated_itm_call() -> None:
    """Near-expiry ITM call: delta rises toward 1 as τ grows → ∂Δ/∂τ > 0 (charm > 0)."""
    g = compute_european_bsm_greeks(
        spot=Decimal("100"),
        strike=Decimal("90"),
        risk_free_rate=Decimal("0.05"),
        dividend_yield=Decimal("0"),
        implied_volatility=Decimal("0.30"),
        expiration_date=date(2026, 6, 8),
        evaluation_date=date(2026, 6, 1),
        side=OptionSide.CALL,
    )
    assert g is not None and g.charm is not None
    assert float(g.charm) > 0


@pytest.mark.unit
def test_volga_positive_for_otm() -> None:
    g = compute_european_bsm_greeks(
        spot=Decimal("100"),
        strike=Decimal("125"),
        risk_free_rate=Decimal("0.05"),
        dividend_yield=Decimal("0"),
        implied_volatility=Decimal("0.25"),
        expiration_date=date(2027, 6, 1),
        evaluation_date=date(2026, 6, 1),
        side=OptionSide.CALL,
    )
    assert g is not None and g.volga is not None
    assert float(g.volga) > 0


@pytest.mark.unit
def test_theoretical_price_matches_mid_when_iv_is_fair() -> None:
    spot = Decimal("100")
    strike = Decimal("100")
    iv = Decimal("0.22")
    g = compute_european_bsm_greeks(
        spot=spot,
        strike=strike,
        risk_free_rate=Decimal("0.04"),
        dividend_yield=Decimal("0"),
        implied_volatility=iv,
        expiration_date=date(2027, 1, 1),
        evaluation_date=date(2026, 1, 1),
        side=OptionSide.CALL,
    )
    assert g is not None and g.theoretical_price is not None
    theo = float(g.theoretical_price)
    bid = theo * 0.999
    ask = theo * 1.001
    mid = (bid + ask) / 2.0
    assert abs(mid - theo) / max(0.01, theo) * 100.0 < 0.2


@pytest.mark.unit
def test_itm_probability_call_near_half_when_d2_near_zero() -> None:
    s = 100.0
    r, q, vol, t = 0.05, 0.0, 0.2, 1.0
    k = s * math.exp((r - q - 0.5 * vol * vol) * t)
    g = compute_european_bsm_greeks(
        spot=Decimal(str(s)),
        strike=Decimal(str(k)),
        risk_free_rate=Decimal(str(r)),
        dividend_yield=Decimal(str(q)),
        implied_volatility=Decimal(str(vol)),
        expiration_date=date(2027, 6, 1),
        evaluation_date=date(2026, 6, 1),
        side=OptionSide.CALL,
    )
    assert g is not None and g.itm_probability is not None
    assert 0.45 < float(g.itm_probability) < 0.55


@pytest.mark.unit
def test_vanna_put_equals_call_same_inputs() -> None:
    common = {
        "spot": Decimal("100"),
        "strike": Decimal("105"),
        "risk_free_rate": Decimal("0.03"),
        "dividend_yield": Decimal("0.01"),
        "implied_volatility": Decimal("0.18"),
        "expiration_date": date(2027, 1, 1),
        "evaluation_date": date(2026, 1, 1),
    }
    gc = compute_european_bsm_greeks(**common, side=OptionSide.CALL)
    gp = compute_european_bsm_greeks(**common, side=OptionSide.PUT)
    assert gc is not None and gp is not None
    assert gc.vanna is not None and gp.vanna is not None
    assert abs(float(gc.vanna) - float(gp.vanna)) < 1e-8
