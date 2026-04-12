"""Unit tests for options positioning engine (deterministic, no live Yahoo)."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from copinance_os.data.analytics.options.positioning import build_options_positioning_dict
from copinance_os.domain.models.market import OptionContract, OptionGreeks, OptionsChain, OptionSide
from copinance_os.domain.models.options_positioning import OptionsPositioningResult


def _gc(strike: float, oi: int, vol: int, iv: float, delta: float, gamma: float) -> OptionContract:
    return OptionContract(
        underlying_symbol="SPY",
        contract_symbol=f"C{strike}",
        side=OptionSide.CALL,
        strike=Decimal(str(strike)),
        expiration_date=date(2026, 1, 16),
        bid=Decimal("1"),
        ask=Decimal("1.1"),
        volume=vol,
        open_interest=oi,
        implied_volatility=Decimal(str(iv / 100.0)) if iv > 2 else Decimal(str(iv)),
        greeks=OptionGreeks(
            delta=Decimal(str(delta)),
            gamma=Decimal(str(gamma)),
            theta=Decimal("0"),
            vega=Decimal("0"),
            rho=Decimal("0"),
        ),
    )


def _gp(strike: float, oi: int, vol: int, iv: float, delta: float, gamma: float) -> OptionContract:
    return OptionContract(
        underlying_symbol="SPY",
        contract_symbol=f"P{strike}",
        side=OptionSide.PUT,
        strike=Decimal(str(strike)),
        expiration_date=date(2026, 1, 16),
        bid=Decimal("1"),
        ask=Decimal("1.1"),
        volume=vol,
        open_interest=oi,
        implied_volatility=Decimal(str(iv / 100.0)) if iv > 2 else Decimal(str(iv)),
        greeks=OptionGreeks(
            delta=Decimal(str(delta)),
            gamma=Decimal(str(gamma)),
            theta=Decimal("0"),
            vega=Decimal("0"),
            rho=Decimal("0"),
        ),
    )


@pytest.fixture
def toy_chain() -> tuple[OptionsChain, list[OptionContract], list[OptionContract]]:
    exp = date(2026, 1, 16)
    calls = [
        _gc(580, 10000, 500, 18.0, 0.52, 0.02),
        _gc(590, 12000, 600, 17.5, 0.48, 0.025),
        _gc(600, 8000, 400, 17.0, 0.25, 0.015),
    ]
    puts = [
        _gp(580, 9000, 450, 19.0, -0.48, 0.02),
        _gp(590, 11000, 550, 18.5, -0.52, 0.022),
        _gp(600, 7000, 350, 18.0, -0.25, 0.014),
    ]
    chain = OptionsChain(
        underlying_symbol="SPY",
        expiration_date=exp,
        available_expirations=[exp],
        underlying_price=Decimal("595"),
        calls=calls,
        puts=puts,
    )
    return chain, calls, puts


@pytest.mark.unit
def test_build_options_positioning_dict_validates(toy_chain: tuple) -> None:
    chain, calls, puts = toy_chain
    quote = {"current_price": 595.0}
    raw = build_options_positioning_dict(chain, calls, puts, quote, "SPY", "near")
    model = OptionsPositioningResult.model_validate(raw)
    assert model.symbol == "SPY"
    assert model.window == "near"
    assert model.market_bias in ("bullish", "bearish", "neutral")
    assert model.signal_categories is not None
    assert len(model.signal_categories.positioning) == 4
    assert model.iv_metrics is not None
    assert model.regime in ("positive_gamma", "negative_gamma", "neutral")


@pytest.mark.unit
def test_toy_near_matches_golden_fixture(toy_chain: tuple) -> None:
    """Regression guard: toy chain output must match checked-in JSON."""
    chain, calls, puts = toy_chain
    raw = build_options_positioning_dict(
        chain, calls, puts, {"current_price": 595.0}, "SPY", "near"
    )
    fixture = (
        Path(__file__).resolve().parents[5] / "fixtures" / "options_positioning" / "toy_near.json"
    )
    expected = json.loads(fixture.read_text(encoding="utf-8"))
    assert raw == expected


@pytest.mark.unit
def test_build_options_positioning_empty_chain() -> None:
    exp = date(2026, 1, 16)
    chain = OptionsChain(
        underlying_symbol="ZZZZ",
        expiration_date=exp,
        available_expirations=[],
        underlying_price=None,
        calls=[],
        puts=[],
    )
    raw = build_options_positioning_dict(chain, [], [], {}, "ZZZZ", "near")
    model = OptionsPositioningResult.model_validate(raw)
    assert model.symbol == "ZZZZ"
    assert model.key_levels == []
