"""Invariant checks for BSM Greek outputs."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

pytest.importorskip("QuantLib")

from copinance_os.data.analytics.options.greeks import compute_european_bsm_greeks
from copinance_os.data.analytics.options.greeks import engine as greeks_engine
from copinance_os.data.analytics.options.greeks.engine import estimate_bsm_greeks_for_options_chain
from copinance_os.domain.models.market import OptionContract, OptionsChain, OptionSide


@pytest.mark.unit
@given(
    spot=st.decimals(min_value="20", max_value="500", allow_nan=False, allow_infinity=False),
    strike=st.decimals(min_value="20", max_value="500", allow_nan=False, allow_infinity=False),
    vol=st.decimals(min_value="0.05", max_value="2.0", allow_nan=False, allow_infinity=False),
)
def test_gamma_is_positive_for_call_and_put_same_inputs(
    spot: Decimal, strike: Decimal, vol: Decimal
) -> None:
    common = {
        "spot": spot,
        "strike": strike,
        "risk_free_rate": Decimal("0.04"),
        "dividend_yield": Decimal("0.01"),
        "implied_volatility": vol,
        "expiration_date": date(2027, 1, 15),
        "evaluation_date": date(2026, 1, 15),
    }
    call = compute_european_bsm_greeks(**common, side=OptionSide.CALL)
    put = compute_european_bsm_greeks(**common, side=OptionSide.PUT)
    assert call is not None and put is not None
    assert call.gamma >= 0
    assert put.gamma >= 0


@pytest.mark.unit
@given(spot=st.decimals(min_value="50", max_value="500", allow_nan=False, allow_infinity=False))
def test_call_delta_decreases_as_strike_increases(spot: Decimal) -> None:
    low_k = compute_european_bsm_greeks(
        spot=spot,
        strike=spot * Decimal("0.9"),
        risk_free_rate=Decimal("0.03"),
        dividend_yield=Decimal("0"),
        implied_volatility=Decimal("0.20"),
        expiration_date=date(2027, 6, 1),
        evaluation_date=date(2026, 6, 1),
        side=OptionSide.CALL,
    )
    high_k = compute_european_bsm_greeks(
        spot=spot,
        strike=spot * Decimal("1.1"),
        risk_free_rate=Decimal("0.03"),
        dividend_yield=Decimal("0"),
        implied_volatility=Decimal("0.20"),
        expiration_date=date(2027, 6, 1),
        evaluation_date=date(2026, 6, 1),
        side=OptionSide.CALL,
    )
    assert low_k is not None and high_k is not None
    assert low_k.delta > high_k.delta


@pytest.mark.unit
@given(
    spot=st.decimals(min_value="20", max_value="500", allow_nan=False, allow_infinity=False),
    strike=st.decimals(min_value="20", max_value="500", allow_nan=False, allow_infinity=False),
    vol=st.decimals(min_value="0.05", max_value="2.0", allow_nan=False, allow_infinity=False),
    rf=st.decimals(min_value="0.0", max_value="0.15", allow_nan=False, allow_infinity=False),
    dte_days=st.integers(min_value=1, max_value=720),
)
def test_primary_greeks_invariants_hold_for_positive_inputs(
    spot: Decimal, strike: Decimal, vol: Decimal, rf: Decimal, dte_days: int
) -> None:
    eval_date = date(2026, 1, 15)
    expiration = date.fromordinal(eval_date.toordinal() + dte_days)
    out = compute_european_bsm_greeks(
        spot=spot,
        strike=strike,
        risk_free_rate=rf,
        dividend_yield=Decimal("0"),
        implied_volatility=vol,
        expiration_date=expiration,
        evaluation_date=eval_date,
        side=OptionSide.CALL,
    )
    assert out is not None
    assert Decimal("-1") <= out.delta <= Decimal("1")
    assert out.gamma >= 0
    assert out.theta <= 0
    assert out.vega >= 0


@pytest.mark.unit
def test_degenerate_inputs_return_none() -> None:
    assert (
        compute_european_bsm_greeks(
            spot=Decimal("0"),
            strike=Decimal("100"),
            risk_free_rate=Decimal("0.03"),
            dividend_yield=Decimal("0"),
            implied_volatility=Decimal("0.2"),
            expiration_date=date(2027, 6, 1),
            evaluation_date=date(2026, 6, 1),
            side=OptionSide.CALL,
        )
        is None
    )
    assert (
        compute_european_bsm_greeks(
            spot=Decimal("100"),
            strike=Decimal("100"),
            risk_free_rate=Decimal("0.03"),
            dividend_yield=Decimal("0"),
            implied_volatility=Decimal("0.2"),
            expiration_date=date(2026, 6, 1),
            evaluation_date=date(2026, 6, 2),
            side=OptionSide.CALL,
        )
        is None
    )
    assert (
        compute_european_bsm_greeks(
            spot=Decimal("100"),
            strike=Decimal("0"),
            risk_free_rate=Decimal("0.03"),
            dividend_yield=Decimal("0"),
            implied_volatility=Decimal("0.2"),
            expiration_date=date(2027, 6, 1),
            evaluation_date=date(2026, 6, 1),
            side=OptionSide.CALL,
        )
        is None
    )
    assert (
        compute_european_bsm_greeks(
            spot=Decimal("100"),
            strike=Decimal("100"),
            risk_free_rate=Decimal("0.03"),
            dividend_yield=Decimal("0"),
            implied_volatility=Decimal("0"),
            expiration_date=date(2027, 6, 1),
            evaluation_date=date(2026, 6, 1),
            side=OptionSide.CALL,
        )
        is None
    )


@pytest.mark.unit
def test_chain_estimation_reuses_single_process_for_shared_market_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quantlib_mod = greeks_engine.QuantLib
    assert quantlib_mod is not None
    original_ctor = quantlib_mod.BlackScholesMertonProcess
    create_count = 0

    def counting_ctor(*args: object, **kwargs: object) -> object:
        nonlocal create_count
        create_count += 1
        return original_ctor(*args, **kwargs)

    monkeypatch.setattr(quantlib_mod, "BlackScholesMertonProcess", counting_ctor)

    eval_date = date(2026, 1, 15)
    exp = date(2027, 1, 15)
    iv = Decimal("0.22")
    calls = [
        OptionContract(
            underlying_symbol="SPY",
            contract_symbol=f"SPY-C-{k}",
            side=OptionSide.CALL,
            strike=Decimal(str(k)),
            expiration_date=exp,
            implied_volatility=iv,
            open_interest=10,
        )
        for k in (95, 100, 105)
    ]
    chain = OptionsChain(
        underlying_symbol="SPY",
        expiration_date=exp,
        available_expirations=[exp],
        underlying_price=Decimal("100"),
        calls=calls,
        puts=[],
    )
    out = estimate_bsm_greeks_for_options_chain(chain, evaluation_date=eval_date)
    assert all(c.greeks is not None for c in out.calls)
    assert create_count == 1
