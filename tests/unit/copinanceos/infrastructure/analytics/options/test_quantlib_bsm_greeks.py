"""Tests for QuantLib-backed Black–Scholes–Merton Greeks."""

from datetime import date
from decimal import Decimal

import pytest

pytest.importorskip("QuantLib")

from copinanceos.domain.models.market import OptionContract, OptionsChain, OptionSide
from copinanceos.infrastructure.analytics.options.quantlib_bsm_greeks import (
    QuantLibBsmGreekEstimator,
    compute_european_bsm_greeks,
    estimate_bsm_greeks_for_options_chain,
)
from copinanceos.infrastructure.config import Settings


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
        "copinanceos.infrastructure.analytics.options.quantlib_bsm_greeks.get_settings",
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
