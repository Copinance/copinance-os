"""Unit tests for options positioning engine (deterministic, no live Yahoo)."""

from __future__ import annotations

import json
import math
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import pytest

from copinance_os.data.analytics.options.positioning import (
    build_options_positioning,
)
from copinance_os.data.analytics.options.positioning.bias import (
    DEFAULT_BIAS_CONFIG,
    compute_signal_agreement,
)
from copinance_os.data.analytics.options.positioning.charm import compute_charm_exposure
from copinance_os.data.analytics.options.positioning.compose import _collapse_duplicate_ratio_vote
from copinance_os.data.analytics.options.positioning.gex import (
    DEFAULT_GEX_CONFIG,
    compute_gamma_regime,
    gex_methodology,
)
from copinance_os.data.analytics.options.positioning.mispricing import compute_mispricing
from copinance_os.data.analytics.options.positioning.moneyness import compute_moneyness_buckets
from copinance_os.data.analytics.options.positioning.pin_risk import compute_pin_risk
from copinance_os.data.analytics.options.positioning.vanna import compute_vanna_exposure
from copinance_os.data.analytics.options.positioning.volatility import compute_volatility_signals
from copinance_os.data.literacy import options_positioning as _pt
from copinance_os.domain.exceptions import ValidationError
from copinance_os.domain.models.entities.profile import FinancialLiteracy
from copinance_os.domain.models.market import OptionContract, OptionGreeks, OptionsChain, OptionSide
from copinance_os.domain.models.options.positioning import OptionsPositioningResult

TOY_AS_OF = date(2026, 1, 9)


def _build_pos_dict(
    chain: OptionsChain,
    calls: list[OptionContract],
    puts: list[OptionContract],
    quote: dict[str, Any],
    symbol: str,
    window: Literal["near", "mid"],
    **kwargs: Any,
) -> dict[str, Any]:
    """Test helper: mirror legacy dict return for fixture / JSON comparisons."""
    return build_options_positioning(
        chain=chain,
        calls=calls,
        puts=puts,
        quote=quote,
        symbol=symbol,
        window=window,
        **kwargs,
    ).model_dump(mode="python")


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
def test_positioning_ignores_available_expirations_without_contract_rows() -> None:
    """Provider calendars may list an earlier expiry than the returned option strip."""
    exp_contracts = date(2026, 4, 17)
    phantom = date(2026, 4, 16)
    calls = [
        _gc(500, 1000, 100, 18.0, 0.5, 0.02).model_copy(update={"expiration_date": exp_contracts}),
    ]
    puts = [
        _gp(500, 1000, 100, 18.0, -0.5, 0.02).model_copy(update={"expiration_date": exp_contracts}),
    ]
    chain = OptionsChain(
        underlying_symbol="SPY",
        expiration_date=exp_contracts,
        available_expirations=[phantom, exp_contracts],
        underlying_price=Decimal("500"),
        calls=calls,
        puts=puts,
    )
    quote = {"current_price": 500.0}
    raw = _build_pos_dict(
        chain,
        calls,
        puts,
        quote,
        "SPY",
        "near",
        as_of_date=exp_contracts,
        enrich_missing_greeks=False,
    )
    model = OptionsPositioningResult.model_validate(raw)
    assert model.symbol == "SPY"
    expiries_used = model.methodology.data_inputs.get("expirations_used", "")
    assert phantom.isoformat() not in expiries_used
    assert exp_contracts.isoformat() in expiries_used


@pytest.mark.unit
def test__build_pos_dict_validates(toy_chain: tuple) -> None:
    chain, calls, puts = toy_chain
    quote = {"current_price": 595.0}
    raw = _build_pos_dict(chain, calls, puts, quote, "SPY", "near", as_of_date=TOY_AS_OF)
    model = OptionsPositioningResult.model_validate(raw)
    assert model.symbol == "SPY"
    assert model.window == "near"
    assert model.methodology.version == "analysis_methodology_v1"
    top_level_spec_ids = {s.id for s in model.methodology.specs}
    assert top_level_spec_ids
    assert "options.positioning.bias" in top_level_spec_ids
    assert "options.positioning.data_quality" in top_level_spec_ids
    assert "options.positioning.flow" not in top_level_spec_ids
    assert model.market_bias in ("bullish", "bearish", "neutral")
    assert model.signal_categories is not None
    assert len(model.signal_categories.positioning.signals) == 6
    assert model.iv_metrics is not None
    assert model.regime in ("positive_gamma", "negative_gamma", "neutral")
    assert model.data_quality is not None and model.data_quality > 0.8
    assert model.dollar_metrics is not None
    assert model.delta_exposure is not None
    assert model.signal_agreement is not None


@pytest.mark.unit
def test_financial_literacy_beginner_changes_analyst_summary(toy_chain: tuple) -> None:
    chain, calls, puts = toy_chain
    quote = {"current_price": 595.0}
    raw_default = _build_pos_dict(chain, calls, puts, quote, "SPY", "near", as_of_date=TOY_AS_OF)
    raw_beginner = _build_pos_dict(
        chain,
        calls,
        puts,
        quote,
        "SPY",
        "near",
        financial_literacy=FinancialLiteracy.BEGINNER,
        as_of_date=TOY_AS_OF,
    )
    assert raw_beginner["analyst_summary"] != raw_default["analyst_summary"]
    assert "aggregate options surface" in raw_default["analyst_summary"]
    assert "more option contracts" in raw_beginner["analyst_summary"]


@pytest.mark.unit
def test_toy_near_matches_golden_fixture(toy_chain: tuple) -> None:
    """Regression guard: toy chain output must match checked-in JSON."""
    chain, calls, puts = toy_chain
    fixture = (
        Path(__file__).resolve().parents[5] / "fixtures" / "options_positioning" / "toy_near.json"
    )
    expected = json.loads(fixture.read_text(encoding="utf-8"))
    raw_json = build_options_positioning(
        chain=chain,
        calls=calls,
        puts=puts,
        quote={"current_price": 595.0},
        symbol="SPY",
        window="near",
        as_of_date=TOY_AS_OF,
    ).model_dump(mode="json")
    raw_json["methodology"].pop("computed_at", None)
    expected["methodology"].pop("computed_at", None)
    assert raw_json == expected


@pytest.mark.unit
def test_toy_near_missing_greeks_matches_golden_fixture(toy_chain: tuple) -> None:
    chain, calls, puts = toy_chain
    calls_missing = [
        calls[0].model_copy(update={"greeks": None}),
        calls[1],
        calls[2].model_copy(update={"greeks": None}),
    ]
    puts_missing = [puts[0], puts[1].model_copy(update={"greeks": None}), puts[2]]
    chain_missing = chain.model_copy(update={"calls": calls_missing, "puts": puts_missing})

    fixture = (
        Path(__file__).resolve().parents[5]
        / "fixtures"
        / "options_positioning"
        / "toy_near_missing_greeks.json"
    )
    expected = json.loads(fixture.read_text(encoding="utf-8"))
    raw_json = build_options_positioning(
        chain=chain_missing,
        calls=calls_missing,
        puts=puts_missing,
        quote={"current_price": 595.0},
        symbol="SPY",
        window="near",
        as_of_date=TOY_AS_OF,
    ).model_dump(mode="json")
    raw_json["methodology"].pop("computed_at", None)
    expected["methodology"].pop("computed_at", None)
    assert raw_json == expected


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
    with pytest.raises(ValidationError, match="No contracts available"):
        _build_pos_dict(chain, [], [], {}, "ZZZZ", "near", as_of_date=TOY_AS_OF)


@pytest.mark.unit
def test_data_quality_low_without_greeks(toy_chain: tuple) -> None:
    chain, calls, puts = toy_chain
    full_dq = _build_pos_dict(
        chain, calls, puts, {"current_price": 595.0}, "SPY", "near", as_of_date=TOY_AS_OF
    )["data_quality"]
    calls_ng = [OptionContract.model_validate(c.model_dump() | {"greeks": None}) for c in calls]
    puts_ng = [OptionContract.model_validate(p.model_dump() | {"greeks": None}) for p in puts]
    raw = _build_pos_dict(
        chain, calls_ng, puts_ng, {"current_price": 595.0}, "SPY", "near", as_of_date=TOY_AS_OF
    )
    assert raw["data_quality"] is not None
    assert raw["data_quality"] < float(full_dq)


@pytest.mark.unit
def test_dollar_metrics_mid_prices(toy_chain: tuple) -> None:
    chain, calls, puts = toy_chain
    raw = _build_pos_dict(
        chain, calls, puts, {"current_price": 595.0}, "SPY", "near", as_of_date=TOY_AS_OF
    )
    dm = raw["dollar_metrics"]
    assert dm["dollar_call_oi"] == pytest.approx(3_150_000.0, rel=1e-6)
    assert dm["dollar_put_oi"] == pytest.approx(2_835_000.0, rel=1e-6)
    assert dm["dollar_put_call_oi_ratio"] == pytest.approx(0.9, rel=1e-6)


@pytest.mark.unit
def test_dollar_metrics_uses_last_price_when_no_bid_ask() -> None:
    exp = date(2026, 2, 20)
    c = OptionContract(
        underlying_symbol="X",
        contract_symbol="XC",
        side=OptionSide.CALL,
        strike=Decimal("100"),
        expiration_date=exp,
        bid=None,
        ask=None,
        last_price=Decimal("2.5"),
        volume=10,
        open_interest=100,
        implied_volatility=Decimal("0.30"),
        greeks=OptionGreeks(
            delta=Decimal("0.5"),
            gamma=Decimal("0.01"),
            theta=Decimal("0"),
            vega=Decimal("0"),
            rho=Decimal("0"),
        ),
    )
    chain = OptionsChain(
        underlying_symbol="X",
        expiration_date=exp,
        available_expirations=[exp],
        underlying_price=Decimal("100"),
        calls=[c],
        puts=[],
    )
    raw = _build_pos_dict(chain, [c], [], {"current_price": 100.0}, "X", "near")
    assert raw["dollar_metrics"]["dollar_call_oi"] == pytest.approx(2.5 * 100 * 100.0)


@pytest.mark.unit
def test_dollar_metrics_zero_prices_no_crash() -> None:
    exp = date(2026, 2, 20)
    c = OptionContract(
        underlying_symbol="X",
        contract_symbol="XC",
        side=OptionSide.CALL,
        strike=Decimal("100"),
        expiration_date=exp,
        bid=Decimal("0"),
        ask=Decimal("0"),
        last_price=None,
        volume=0,
        open_interest=50,
        implied_volatility=Decimal("0.25"),
        greeks=None,
    )
    chain = OptionsChain(
        underlying_symbol="X",
        expiration_date=exp,
        available_expirations=[exp],
        underlying_price=Decimal("100"),
        calls=[c],
        puts=[],
    )
    raw = _build_pos_dict(chain, [c], [], {"current_price": 100.0}, "X", "near")
    assert raw["dollar_metrics"]["dollar_call_oi"] == 0.0


@pytest.mark.unit
def test_gex_per_strike_matches_toy(toy_chain: tuple) -> None:
    chain, calls, puts = toy_chain
    raw = _build_pos_dict(
        chain, calls, puts, {"current_price": 595.0}, "SPY", "near", as_of_date=TOY_AS_OF
    )
    by_k = {x["strike"]: x["gex_value"] for x in raw["gex_profile"]}
    assert by_k[590.0] == pytest.approx(3_451_000.0, rel=1e-6)
    assert by_k[580.0] == pytest.approx(1_190_000.0, rel=1e-6)
    assert by_k[600.0] == pytest.approx(1_309_000.0, rel=1e-6)
    assert raw["gamma_flip_strike"] is None


@pytest.mark.unit
def test_gamma_flip_interpolated() -> None:
    """Two-strike front expiry: cumulative GEX crosses zero between strikes."""
    exp = date(2026, 3, 20)
    spot = 150.0
    mult = 100.0 * spot
    # Strike 100: net +5000; strike 200: net -12000 -> cumulative crosses between 100 and 200.
    calls = [
        OptionContract(
            underlying_symbol="GF",
            contract_symbol="GF100C",
            side=OptionSide.CALL,
            strike=Decimal("100"),
            expiration_date=exp,
            bid=Decimal("1"),
            ask=Decimal("1"),
            volume=1,
            open_interest=10,
            implied_volatility=Decimal("0.2"),
            greeks=OptionGreeks(
                delta=Decimal("0.5"),
                gamma=Decimal("0.05"),
                theta=Decimal("0"),
                vega=Decimal("0"),
                rho=Decimal("0"),
            ),
        ),
    ]
    puts = [
        OptionContract(
            underlying_symbol="GF",
            contract_symbol="GF200P",
            side=OptionSide.PUT,
            strike=Decimal("200"),
            expiration_date=exp,
            bid=Decimal("1"),
            ask=Decimal("1"),
            volume=1,
            open_interest=100,
            implied_volatility=Decimal("0.2"),
            greeks=OptionGreeks(
                delta=Decimal("-0.5"),
                gamma=Decimal("0.08"),
                theta=Decimal("0"),
                vega=Decimal("0"),
                rho=Decimal("0"),
            ),
        ),
    ]
    g_call = 0.05 * 10 * mult
    g_put = 0.08 * 100 * mult
    assert g_call > 0 and g_put > 0
    net_100 = g_call
    net_200 = -g_put
    assert net_100 > 0 and net_200 < 0
    chain = OptionsChain(
        underlying_symbol="GF",
        expiration_date=exp,
        available_expirations=[exp],
        underlying_price=Decimal(str(spot)),
        calls=calls,
        puts=puts,
    )
    raw = _build_pos_dict(
        chain, calls, puts, {"current_price": spot}, "GF", "near", as_of_date=date(2026, 3, 1)
    )
    flip = raw["gamma_flip_strike"]
    assert flip is not None
    assert float(flip) == pytest.approx(106.25, rel=1e-4)
    # Spot (150) is above the flip strike (~106.25), so gamma-flip-vs-spot casts a
    # genuine directional vote here -- unlike net-gamma/gamma-regime, which never do.
    gamma_signals = raw["signal_categories"]["gamma"]["signals"]
    flip_row = next(
        s
        for s in gamma_signals
        if s["name"] == _pt.name_gamma_flip_strike(FinancialLiteracy.INTERMEDIATE)
    )
    assert flip_row["direction"] == "bullish"


@pytest.mark.unit
def test_gex_profile_empty_without_greeks() -> None:
    exp = date(2026, 4, 15)
    c = OptionContract(
        underlying_symbol="NG",
        contract_symbol="NGC",
        side=OptionSide.CALL,
        strike=Decimal("50"),
        expiration_date=exp,
        bid=Decimal("1"),
        ask=Decimal("1.1"),
        volume=1,
        open_interest=1000,
        implied_volatility=Decimal("0.3"),
        greeks=None,
    )
    chain = OptionsChain(
        underlying_symbol="NG",
        expiration_date=exp,
        available_expirations=[exp],
        underlying_price=Decimal("50"),
        calls=[c],
        puts=[],
    )
    raw = _build_pos_dict(chain, [c], [], {"current_price": 50.0}, "NG", "near")
    assert raw["gex_profile"] == []
    assert raw["top_positive_gex"] == []


@pytest.mark.unit
def test_delta_exposure_toy(toy_chain: tuple) -> None:
    chain, calls, puts = toy_chain
    raw = _build_pos_dict(
        chain, calls, puts, {"current_price": 595.0}, "SPY", "near", as_of_date=TOY_AS_OF
    )
    dex = raw["delta_exposure"]
    assert dex["net_delta"] == pytest.approx(117_000.0, rel=1e-6)
    assert dex["dollar_delta"] == pytest.approx(117_000.0 * 595.0, rel=1e-6)


@pytest.mark.unit
def test_delta_exposure_zero_without_greeks() -> None:
    exp = date(2026, 5, 1)
    c = OptionContract(
        underlying_symbol="Z",
        contract_symbol="ZC",
        side=OptionSide.CALL,
        strike=Decimal("10"),
        expiration_date=exp,
        bid=Decimal("1"),
        ask=Decimal("1"),
        volume=1,
        open_interest=500,
        implied_volatility=Decimal("0.4"),
        greeks=None,
    )
    chain = OptionsChain(
        underlying_symbol="Z",
        expiration_date=exp,
        available_expirations=[exp],
        underlying_price=Decimal("10"),
        calls=[c],
        puts=[],
    )
    raw = _build_pos_dict(chain, [c], [], {"current_price": 10.0}, "Z", "near")
    assert raw["delta_exposure"]["net_delta"] == 0.0


@pytest.mark.unit
def test_oi_clusters_enhanced_walls(toy_chain: tuple) -> None:
    chain, calls, puts = toy_chain
    raw = _build_pos_dict(
        chain, calls, puts, {"current_price": 595.0}, "SPY", "near", as_of_date=TOY_AS_OF
    )
    assert raw["call_wall"] == 590.0
    assert raw["put_wall"] == 590.0
    top = raw["oi_clusters_enhanced"][0]
    assert top["strike"] == 590.0
    assert top["call_oi"] == 12000.0 and top["put_oi"] == 11000.0


@pytest.mark.unit
def test_brenner_subrahmanyam_implied_move(toy_chain: tuple) -> None:
    chain, calls, puts = toy_chain
    raw = _build_pos_dict(
        chain, calls, puts, {"current_price": 595.0}, "SPY", "near", as_of_date=TOY_AS_OF
    )
    detail = raw["implied_move_detail"]
    assert detail is not None
    straddle = 2.1
    spot = 595.0
    dte = 7
    t = dte / 365.0
    expected_ann = (straddle / (0.798 * spot * math.sqrt(t))) * 100.0
    assert detail["dte"] == dte
    assert detail["annualized_iv"] == pytest.approx(expected_ann, rel=1e-4)
    assert detail["daily_implied_move_pct"] == pytest.approx(
        expected_ann / math.sqrt(252.0), rel=1e-4
    )
    assert detail["period_implied_move_pct"] == pytest.approx(
        expected_ann * math.sqrt(dte / 365.0), rel=1e-4
    )
    # Period figure must be derived using the same calendar-day convention as the
    # annualization (dte/365), not trading-day scaling (dte/252) -- otherwise it
    # overstates the move by ~1.2x relative to the model's own math. This identity
    # (period == raw_straddle_pct / straddle_ann_factor) holds only when both use
    # calendar days consistently.
    assert detail["period_implied_move_pct"] / detail["raw_straddle_pct"] == pytest.approx(
        1.0 / 0.798, rel=1e-3
    )


@pytest.mark.unit
def test_implied_move_detail_none_without_straddle() -> None:
    exp = date(2026, 6, 18)
    c = OptionContract(
        underlying_symbol="Q",
        contract_symbol="QC",
        side=OptionSide.CALL,
        strike=Decimal("100"),
        expiration_date=exp,
        bid=Decimal("0"),
        ask=Decimal("0"),
        volume=0,
        open_interest=1,
        implied_volatility=Decimal("0.2"),
        greeks=None,
    )
    p = OptionContract(
        underlying_symbol="Q",
        contract_symbol="QP",
        side=OptionSide.PUT,
        strike=Decimal("100"),
        expiration_date=exp,
        bid=Decimal("0"),
        ask=Decimal("0"),
        volume=0,
        open_interest=1,
        implied_volatility=Decimal("0.2"),
        greeks=None,
    )
    chain = OptionsChain(
        underlying_symbol="Q",
        expiration_date=exp,
        available_expirations=[exp],
        underlying_price=Decimal("100"),
        calls=[c],
        puts=[p],
    )
    raw = _build_pos_dict(chain, [c], [p], {"current_price": 100.0}, "Q", "near")
    assert raw["implied_move_detail"] is None


@pytest.mark.unit
def test_implied_move_dte_one_day() -> None:
    exp = date(2026, 7, 10)
    c = OptionContract(
        underlying_symbol="D",
        contract_symbol="DC",
        side=OptionSide.CALL,
        strike=Decimal("50"),
        expiration_date=exp,
        bid=Decimal("1"),
        ask=Decimal("1"),
        volume=1,
        open_interest=10,
        implied_volatility=Decimal("0.25"),
        greeks=OptionGreeks(
            delta=Decimal("0.5"),
            gamma=Decimal("0.02"),
            theta=Decimal("0"),
            vega=Decimal("0"),
            rho=Decimal("0"),
        ),
    )
    p = OptionContract(
        underlying_symbol="D",
        contract_symbol="DP",
        side=OptionSide.PUT,
        strike=Decimal("50"),
        expiration_date=exp,
        bid=Decimal("1"),
        ask=Decimal("1"),
        volume=1,
        open_interest=10,
        implied_volatility=Decimal("0.25"),
        greeks=OptionGreeks(
            delta=Decimal("-0.5"),
            gamma=Decimal("0.02"),
            theta=Decimal("0"),
            vega=Decimal("0"),
            rho=Decimal("0"),
        ),
    )
    chain = OptionsChain(
        underlying_symbol="D",
        expiration_date=exp,
        available_expirations=[exp],
        underlying_price=Decimal("50"),
        calls=[c],
        puts=[p],
    )
    raw = _build_pos_dict(
        chain,
        [c],
        [p],
        {"current_price": 50.0},
        "D",
        "near",
        as_of_date=date(2026, 7, 9),
    )
    assert raw["implied_move_detail"]["dte"] == 1


@pytest.mark.unit
@pytest.mark.parametrize("atm_iv_pct", [1.0, 18.0, 99.0])
def test_iv_rank_signal_direction_always_neutral(toy_chain: tuple, atm_iv_pct: float) -> None:
    """IV rank is a within-chain cross-sectional percentile, structurally biased low by
    the smile (ATM sits below OTM skew). It must never vote a direction, regardless of
    how extreme the percentile is -- only the ATM IV level signal may carry direction.
    """
    chain, calls, puts = toy_chain
    nearest_exp = calls[0].expiration_date.isoformat()
    # Construct an IV sample distribution where the ATM print sits at either extreme,
    # so the naive percentile-based direction logic would previously have fired
    # "bearish" (high rank) or "bullish" (low rank).
    all_iv_samples = [1.0, 5.0, 10.0, 15.0, 20.0, 50.0, 99.0]
    signals, partial = compute_volatility_signals(
        calls,
        puts,
        nearest_exp,
        595.0,
        all_iv_samples,
        FinancialLiteracy.INTERMEDIATE,
    )
    assert len(signals) == 2
    rank_signal = signals[1]
    assert rank_signal["direction"] == "neutral"
    # The percentile value itself is still computed and exposed for display.
    assert "value" in rank_signal
    assert partial["iv_rank"] == pytest.approx(rank_signal["value"], rel=1e-3)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("skew25", "expected_regime"),
    [(3.5, "steep_put"), (-2.0, "call_skewed"), (0.0, "normal")],
)
def test_skew_regime_classification(skew25: float, expected_regime: str) -> None:
    exp = date(2026, 8, 15)

    def mk(side: OptionSide, delta: float, iv: float) -> OptionContract:
        return OptionContract(
            underlying_symbol="SK",
            contract_symbol="SKX",
            side=side,
            strike=Decimal("100"),
            expiration_date=exp,
            bid=Decimal("1"),
            ask=Decimal("1"),
            volume=10,
            open_interest=100,
            implied_volatility=Decimal(str(iv / 100.0)),
            greeks=OptionGreeks(
                delta=Decimal(str(delta)),
                gamma=Decimal("0.01"),
                theta=Decimal("0"),
                vega=Decimal("0"),
                rho=Decimal("0"),
            ),
        )

    iv_call = 20.0
    iv_put = iv_call + skew25
    calls = [mk(OptionSide.CALL, 0.25, iv_call)]
    puts = [mk(OptionSide.PUT, -0.25, iv_put)]
    chain = OptionsChain(
        underlying_symbol="SK",
        expiration_date=exp,
        available_expirations=[exp],
        underlying_price=Decimal("100"),
        calls=calls,
        puts=puts,
    )
    raw = _build_pos_dict(
        chain, calls, puts, {"current_price": 100.0}, "SK", "near", as_of_date=date(2026, 8, 1)
    )
    assert raw["iv_metrics"]["skew_regime"] == expected_regime


@pytest.mark.unit
def test_butterfly_positive_when_wings_rich() -> None:
    exp = date(2026, 9, 1)

    def leg(
        side: OptionSide, strike: float, delta: float, iv: float, sym: str = "BF"
    ) -> OptionContract:
        return OptionContract(
            underlying_symbol=sym,
            contract_symbol=f"{sym}X",
            side=side,
            strike=Decimal(str(strike)),
            expiration_date=exp,
            bid=Decimal("1"),
            ask=Decimal("1"),
            volume=10,
            open_interest=100,
            implied_volatility=Decimal(str(iv / 100.0)),
            greeks=OptionGreeks(
                delta=Decimal(str(delta)),
                gamma=Decimal("0.01"),
                theta=Decimal("0"),
                vega=Decimal("0"),
                rho=Decimal("0"),
            ),
        )

    calls = [
        leg(OptionSide.CALL, 100.0, 0.5, 20.0),
        leg(OptionSide.CALL, 105.0, 0.25, 26.0),
    ]
    puts = [
        leg(OptionSide.PUT, 100.0, -0.5, 20.0),
        leg(OptionSide.PUT, 95.0, -0.25, 26.0),
    ]
    chain = OptionsChain(
        underlying_symbol="BF",
        expiration_date=exp,
        available_expirations=[exp],
        underlying_price=Decimal("100"),
        calls=calls,
        puts=puts,
    )
    raw = _build_pos_dict(
        chain, calls, puts, {"current_price": 100.0}, "BF", "near", as_of_date=date(2026, 8, 15)
    )
    assert raw["iv_metrics"]["butterfly_25_delta"] == pytest.approx(6.0, rel=1e-6)


@pytest.mark.unit
def test_25_delta_strike_selection_excludes_none_delta_contract() -> None:
    """A contract with a genuinely missing delta must never win the nearest-to-25-delta
    search via a fake ``0.0`` substitution.

    Without the fix, ``numeric_greek(c, "delta") or 0.0`` would let the None-delta call
    below (whose fake key is ``abs(0.0 - 0.25) == 0.25``) beat the only real candidate
    (delta 0.6, key ``abs(0.6 - 0.25) == 0.35``), incorrectly picking the missing-delta
    contract's IV (30%) for the skew calculation instead of the real one (20%).
    """
    exp = date(2026, 11, 1)

    def leg(side: OptionSide, strike: float, delta: float | None, iv: float) -> OptionContract:
        return OptionContract(
            underlying_symbol="ND",
            contract_symbol="NDX",
            side=side,
            strike=Decimal(str(strike)),
            expiration_date=exp,
            bid=Decimal("1"),
            ask=Decimal("1"),
            volume=10,
            open_interest=100,
            implied_volatility=Decimal(str(iv / 100.0)),
            greeks=(
                OptionGreeks(
                    delta=Decimal(str(delta)),
                    gamma=Decimal("0.01"),
                    theta=Decimal("0"),
                    vega=Decimal("0"),
                    rho=Decimal("0"),
                )
                if delta is not None
                else None
            ),
        )

    calls = [
        leg(OptionSide.CALL, 101.0, None, 30.0),  # missing delta -- must be excluded
        leg(OptionSide.CALL, 110.0, 0.6, 20.0),  # only real candidate
    ]
    puts = [leg(OptionSide.PUT, 90.0, -0.25, 22.0)]
    chain = OptionsChain(
        underlying_symbol="ND",
        expiration_date=exp,
        available_expirations=[exp],
        underlying_price=Decimal("100"),
        calls=calls,
        puts=puts,
    )
    raw = _build_pos_dict(
        chain, calls, puts, {"current_price": 100.0}, "ND", "near", as_of_date=date(2026, 10, 15)
    )
    # put_iv (22.0) - call_iv should use the real 0.6-delta call's IV (20.0), not the
    # None-delta call's IV (30.0).
    assert raw["iv_metrics"]["skew_25_delta"] == pytest.approx(2.0, rel=1e-6)


@pytest.mark.unit
def test_skew_10_delta_computed() -> None:
    exp = date(2026, 10, 1)

    def leg(side: OptionSide, delta: float, iv: float) -> OptionContract:
        return OptionContract(
            underlying_symbol="T10",
            contract_symbol="T10X",
            side=side,
            strike=Decimal("100"),
            expiration_date=exp,
            bid=Decimal("1"),
            ask=Decimal("1"),
            volume=10,
            open_interest=100,
            implied_volatility=Decimal(str(iv / 100.0)),
            greeks=OptionGreeks(
                delta=Decimal(str(delta)),
                gamma=Decimal("0.01"),
                theta=Decimal("0"),
                vega=Decimal("0"),
                rho=Decimal("0"),
            ),
        )

    calls = [leg(OptionSide.CALL, 0.10, 18.0)]
    puts = [leg(OptionSide.PUT, -0.10, 22.0)]
    chain = OptionsChain(
        underlying_symbol="T10",
        expiration_date=exp,
        available_expirations=[exp],
        underlying_price=Decimal("100"),
        calls=calls,
        puts=puts,
    )
    raw = _build_pos_dict(
        chain, calls, puts, {"current_price": 100.0}, "T10", "near", as_of_date=date(2026, 9, 15)
    )
    assert raw["iv_metrics"]["skew_10_delta"] == pytest.approx(4.0, rel=1e-6)


@pytest.mark.unit
def test_bias_weight_constants_exposed() -> None:
    assert DEFAULT_BIAS_CONFIG.weights["call_oi_ratio"] == pytest.approx(1.8)
    assert DEFAULT_BIAS_CONFIG.weights["net_delta"] == pytest.approx(1.2)
    assert "dollar_put_call_oi_ratio" in DEFAULT_BIAS_CONFIG.ranges


@pytest.mark.unit
def test_dollar_weighting_changes_bias_vs_zero_mids(toy_chain: tuple) -> None:
    """When all mids are zero, dollar flow share is unavailable and bias scoring falls back."""
    chain, calls, puts = toy_chain

    def zero_mid_call(c: OptionContract) -> OptionContract:
        return OptionContract.model_validate(
            c.model_dump()
            | {"bid": Decimal("0"), "ask": Decimal("0"), "last_price": None, "volume": c.volume}
        )

    def zero_mid_put(p: OptionContract) -> OptionContract:
        return OptionContract.model_validate(
            p.model_dump()
            | {"bid": Decimal("0"), "ask": Decimal("0"), "last_price": None, "volume": p.volume}
        )

    calls_z = [zero_mid_call(c) for c in calls]
    puts_z = [zero_mid_put(p) for p in puts]
    with_mid = _build_pos_dict(
        chain, calls, puts, {"current_price": 595.0}, "SPY", "near", as_of_date=TOY_AS_OF
    )
    zero_mid = _build_pos_dict(
        chain, calls_z, puts_z, {"current_price": 595.0}, "SPY", "near", as_of_date=TOY_AS_OF
    )
    assert zero_mid["dollar_metrics"]["dollar_call_volume"] == 0.0
    assert (
        abs(float(with_mid["bullish_probability"]) - float(zero_mid["bullish_probability"])) > 1e-4
    )


@pytest.mark.unit
def test_data_quality_modulates_confidence(toy_chain: tuple) -> None:
    chain, calls, puts = toy_chain
    full = _build_pos_dict(
        chain, calls, puts, {"current_price": 595.0}, "SPY", "near", as_of_date=TOY_AS_OF
    )
    calls_ng = [OptionContract.model_validate(c.model_dump() | {"greeks": None}) for c in calls]
    puts_ng = [OptionContract.model_validate(p.model_dump() | {"greeks": None}) for p in puts]
    low_dq = _build_pos_dict(
        chain, calls_ng, puts_ng, {"current_price": 595.0}, "SPY", "near", as_of_date=TOY_AS_OF
    )
    assert full["data_quality"] > low_dq["data_quality"]
    assert full["confidence"] > low_dq["confidence"]


@pytest.mark.unit
def test_signal_agreement_strong_bullish_on_toy(toy_chain: tuple) -> None:
    chain, calls, puts = toy_chain
    raw = _build_pos_dict(
        chain, calls, puts, {"current_price": 595.0}, "SPY", "near", as_of_date=TOY_AS_OF
    )
    assert raw["signal_agreement"] == "strong_bullish"


@pytest.mark.unit
def test_gex_methodology_documents_scope_split() -> None:
    """Regime is scored over the whole book; profile/flip-strike is nearest-expiry
    only. This scope split is confusing enough (two related-but-different scopes)
    that the methodology spec must call it out explicitly.
    """
    spec = gex_methodology(DEFAULT_GEX_CONFIG)
    assumptions_text = " ".join(spec.assumptions).lower()
    assert "whole book" in assumptions_text
    assert "all expirations" in assumptions_text
    assert "nearest expiration" in assumptions_text


@pytest.mark.unit
def test_gamma_regime_signals_never_vote_direction(toy_chain: tuple) -> None:
    """Net gamma / gamma regime describe a volatility regime, not a directional bet.

    They must never contribute a bullish/bearish vote to signal agreement -- only
    net-delta and gamma-flip-vs-spot are genuinely directional among gamma signals.
    The regime is still classified and explained for display purposes.
    """
    chain, calls, puts = toy_chain
    lit = FinancialLiteracy.INTERMEDIATE
    signals, net, regime, _expl = compute_gamma_regime(calls, puts, 595.0, lit)
    assert regime == "positive_gamma"
    assert net > 0  # a real directional-looking value is present...
    net_gamma_row = next(s for s in signals if s["name"] == _pt.name_net_gamma(lit))
    regime_row = next(s for s in signals if s["name"] == _pt.name_gamma_regime(lit))
    # ...but neither row casts a vote.
    assert net_gamma_row["direction"] == "neutral"
    assert regime_row["direction"] == "neutral"


@pytest.mark.unit
def test_gamma_flip_and_net_delta_remain_directional_votes(toy_chain: tuple) -> None:
    """Only net-delta and gamma-flip-vs-spot vote among gamma-related signals."""
    chain, calls, puts = toy_chain
    raw = _build_pos_dict(
        chain, calls, puts, {"current_price": 595.0}, "SPY", "near", as_of_date=TOY_AS_OF
    )
    gamma_signals = raw["signal_categories"]["gamma"]["signals"]
    directions_by_name = {s["name"]: s["direction"] for s in gamma_signals}
    assert directions_by_name[_pt.name_net_gamma(FinancialLiteracy.INTERMEDIATE)] == "neutral"
    assert directions_by_name[_pt.name_gamma_regime(FinancialLiteracy.INTERMEDIATE)] == "neutral"
    # Gamma-flip-vs-spot is genuinely directional (bullish/bearish/neutral depending
    # on whether the front expiry's cumulative GEX actually flips sign); for this toy
    # chain there's no sign change so it settles on "neutral" -- what matters is that
    # it is computed independently from spot-vs-flip-strike, not forced neutral like
    # the regime signals above.
    assert directions_by_name[_pt.name_gamma_flip_strike(FinancialLiteracy.INTERMEDIATE)] in (
        "bullish",
        "bearish",
        "neutral",
    )
    assert directions_by_name[_pt.name_net_delta_exposure(FinancialLiteracy.INTERMEDIATE)] in (
        "bullish",
        "bearish",
    )


@pytest.mark.unit
def test_collapse_duplicate_put_call_ratio_vote() -> None:
    """Only one P/C-ratio vote is counted even when both variants are present."""
    signals = [
        {"name": "Put/Call OI Ratio", "direction": "bearish"},
        {"name": "Dollar Put/Call OI Ratio", "direction": "bullish"},
        {"name": "Call OI Share", "direction": "neutral"},
    ]
    collapsed = _collapse_duplicate_ratio_vote(
        signals, dollar_name="Dollar Put/Call OI Ratio", contract_name="Put/Call OI Ratio"
    )
    names = {s["name"] for s in collapsed}
    assert "Put/Call OI Ratio" not in names
    assert "Dollar Put/Call OI Ratio" in names
    assert len(collapsed) == 2

    # Falls back to the contract-count variant when the dollar variant is absent.
    signals_no_dollar = [s for s in signals if s["name"] != "Dollar Put/Call OI Ratio"]
    collapsed_fallback = _collapse_duplicate_ratio_vote(
        signals_no_dollar, dollar_name="Dollar Put/Call OI Ratio", contract_name="Put/Call OI Ratio"
    )
    assert collapsed_fallback == signals_no_dollar


@pytest.mark.unit
def test_signal_agreement_counts_single_pc_ratio_vote_not_double(toy_chain: tuple) -> None:
    """Both P/C ratio variants exist for the toy chain, but agreement must reflect
    only one vote for that pair rather than two near-duplicate votes.
    """
    lit = FinancialLiteracy.INTERMEDIATE
    contract_dir = "bearish"
    dollar_dir = "bearish"
    positioning_with_both = [
        {"name": _pt.name_put_call_oi(lit), "direction": contract_dir},
        {"name": _pt.name_dollar_put_call_oi(lit), "direction": dollar_dir},
        {"name": "Neutral Signal", "direction": "neutral"},
    ]
    collapsed = _collapse_duplicate_ratio_vote(
        positioning_with_both,
        dollar_name=_pt.name_dollar_put_call_oi(lit),
        contract_name=_pt.name_put_call_oi(lit),
    )
    agreement_collapsed = compute_signal_agreement(collapsed, [], [])
    agreement_uncollapsed = compute_signal_agreement(positioning_with_both, [], [])
    # Uncollapsed double-counts the pair (2 bearish votes -> strong agreement);
    # collapsed reflects the single true vote (1 bearish vote, still strong, but not
    # double-weighted against other signals in a larger mixed set).
    assert agreement_uncollapsed == "strong_bearish"
    assert agreement_collapsed == "strong_bearish"
    mixed_with_both = [
        *positioning_with_both,
        {"name": "Other Bullish", "direction": "bullish"},
    ]
    mixed_collapsed = _collapse_duplicate_ratio_vote(
        mixed_with_both,
        dollar_name=_pt.name_dollar_put_call_oi(lit),
        contract_name=_pt.name_put_call_oi(lit),
    )
    # 1 bearish (collapsed) vs 1 bullish -> mixed, not skewed bearish by double count.
    assert compute_signal_agreement(mixed_collapsed, [], []) == "mixed"
    # Without collapsing, the duplicate P/C vote would incorrectly tip it bearish.
    assert compute_signal_agreement(mixed_with_both, [], []) == "moderate_bearish"


@pytest.mark.unit
def test_enrich_missing_greeks_fills_dex_when_quantlib_installed() -> None:
    """``enrich_missing_greeks`` uses QuantLib BSM for rows with ``greeks is None``."""
    pytest.importorskip("QuantLib")
    exp = date(2027, 3, 28)
    c = OptionContract(
        underlying_symbol="ENR",
        contract_symbol="ENRC",
        side=OptionSide.CALL,
        strike=Decimal("400"),
        expiration_date=exp,
        bid=Decimal("1"),
        ask=Decimal("1.1"),
        volume=10,
        open_interest=500,
        implied_volatility=Decimal("0.18"),
        greeks=None,
    )
    chain = OptionsChain(
        underlying_symbol="ENR",
        expiration_date=exp,
        available_expirations=[exp],
        underlying_price=Decimal("400"),
        calls=[c],
        puts=[],
    )
    as_of = date(2026, 3, 28)
    without = _build_pos_dict(
        chain,
        [c],
        [],
        {"current_price": 400.0},
        "ENR",
        "near",
        as_of_date=as_of,
        enrich_missing_greeks=False,
    )
    with_enrich = _build_pos_dict(
        chain,
        [c],
        [],
        {"current_price": 400.0},
        "ENR",
        "near",
        as_of_date=as_of,
        enrich_missing_greeks=True,
    )
    assert without["delta_exposure"]["net_delta"] == 0.0
    assert with_enrich["delta_exposure"]["net_delta"] != 0.0


def _contract_v(
    *,
    strike: float,
    side: OptionSide,
    oi: int,
    delta: float,
    gamma: float,
    vanna: float | None = None,
    charm: float | None = None,
    theo: Decimal | None = None,
    itm_p: Decimal | None = None,
    exp: date | None = None,
    vol: int = 0,
    iv: float = 18.0,
) -> OptionContract:
    e = exp or date(2026, 3, 20)
    og = OptionGreeks(
        delta=Decimal(str(delta)),
        gamma=Decimal(str(gamma)),
        theta=Decimal("0"),
        vega=Decimal("0.1"),
        rho=Decimal("0"),
        vanna=Decimal(str(vanna)) if vanna is not None else None,
        charm=Decimal(str(charm)) if charm is not None else None,
        theoretical_price=theo,
        itm_probability=itm_p,
    )
    return OptionContract(
        underlying_symbol="X",
        contract_symbol=f"{'C' if side == OptionSide.CALL else 'P'}{strike}",
        side=side,
        strike=Decimal(str(strike)),
        expiration_date=e,
        bid=Decimal("1"),
        ask=Decimal("1.1"),
        volume=vol,
        open_interest=oi,
        implied_volatility=Decimal(str(iv / 100.0)),
        greeks=og,
    )


@pytest.mark.unit
def test_vanna_exposure_computation() -> None:
    exp = date(2026, 3, 20)
    calls = [
        _contract_v(strike=100, side=OptionSide.CALL, oi=1000, delta=0.5, gamma=0.01, vanna=0.002),
    ]
    puts = [
        _contract_v(strike=100, side=OptionSide.PUT, oi=500, delta=-0.5, gamma=0.01, vanna=0.002),
    ]
    bundle = compute_vanna_exposure(calls, puts, exp.isoformat(), 100.0)
    vex = bundle["vanna_exposure"]
    assert vex is not None
    # call: 0.002 * 1000 * 100 = 200; put: 0.002 * 500 * 100 = 100; net = 100
    assert vex["net_vanna"] == pytest.approx(100.0, rel=1e-6)
    assert vex["call_vanna_exposure"] == pytest.approx(200.0, rel=1e-6)
    assert vex["put_vanna_exposure"] == pytest.approx(100.0, rel=1e-6)


@pytest.mark.unit
def test_vanna_flip_strike() -> None:
    exp = date(2026, 3, 20)
    exp_s = exp.isoformat()
    # Per-strike net: +10k at 100 then −20k at 101 → cumulative crosses zero between strikes.
    calls = [
        _contract_v(strike=100, side=OptionSide.CALL, oi=1000, delta=0.5, gamma=0.01, vanna=0.001),
    ]
    puts = [
        _contract_v(strike=101, side=OptionSide.PUT, oi=1000, delta=-0.5, gamma=0.01, vanna=0.002),
    ]
    bundle = compute_vanna_exposure(calls, puts, exp_s, 100.0)
    assert bundle["vanna_exposure"]["vanna_flip_strike"] is not None


@pytest.mark.unit
def test_vanna_exposure_no_vanna_on_contracts() -> None:
    exp = date(2026, 3, 20)
    c = _contract_v(strike=100, side=OptionSide.CALL, oi=1000, delta=0.5, gamma=0.01, vanna=None)
    p = _contract_v(strike=100, side=OptionSide.PUT, oi=1000, delta=-0.5, gamma=0.01, vanna=None)
    bundle = compute_vanna_exposure([c], [p], exp.isoformat(), 50.0)
    assert bundle["vanna_exposure"]["net_vanna"] == 0.0
    assert bundle["vanna_profile"] == []


@pytest.mark.unit
def test_charm_exposure_aggregate_and_drift() -> None:
    calls = [
        _contract_v(
            strike=100,
            side=OptionSide.CALL,
            oi=2000,
            delta=0.6,
            gamma=0.01,
            charm=0.0001,
            exp=date(2026, 4, 1),
        ),
    ]
    puts: list[OptionContract] = []
    ch = compute_charm_exposure(calls, puts)["charm_exposure"]
    assert ch["net_charm"] == pytest.approx(20.0, rel=1e-6)
    assert ch["overnight_delta_drift"] == "selling_pressure"


@pytest.mark.unit
def test_charm_neutral_when_flat() -> None:
    c = _contract_v(
        strike=100,
        side=OptionSide.CALL,
        oi=10,
        delta=0.5,
        gamma=0.01,
        charm=0.0,
        exp=date(2026, 4, 1),
    )
    ch = compute_charm_exposure([c], [])["charm_exposure"]
    assert ch["overnight_delta_drift"] == "neutral"


@pytest.mark.unit
def test_mispricing_detects_call_demand() -> None:
    calls = [
        _contract_v(
            strike=100,
            side=OptionSide.CALL,
            oi=100,
            delta=0.5,
            gamma=0.01,
            theo=Decimal("1.0"),
            exp=date(2026, 5, 1),
        ),
    ]
    calls[0] = OptionContract.model_validate(
        calls[0].model_dump() | {"bid": Decimal("1.1"), "ask": Decimal("1.15")}
    )
    puts = [
        _contract_v(
            strike=100,
            side=OptionSide.PUT,
            oi=100,
            delta=-0.5,
            gamma=0.01,
            theo=Decimal("1.0"),
            exp=date(2026, 5, 1),
        ),
    ]
    puts[0] = OptionContract.model_validate(
        puts[0].model_dump() | {"bid": Decimal("0.85"), "ask": Decimal("0.9")}
    )
    mp = compute_mispricing(calls, puts)
    assert mp is not None
    assert mp["mispricing"]["sentiment"] == "call_demand"


@pytest.mark.unit
def test_mispricing_neutral_when_fair() -> None:
    theo = Decimal("2.0")
    c = _contract_v(
        strike=100,
        side=OptionSide.CALL,
        oi=10,
        delta=0.5,
        gamma=0.01,
        theo=theo,
        exp=date(2026, 5, 1),
    )
    c = OptionContract.model_validate(
        c.model_dump() | {"bid": Decimal("2.0"), "ask": Decimal("2.0")}
    )
    p = _contract_v(
        strike=100,
        side=OptionSide.PUT,
        oi=10,
        delta=-0.5,
        gamma=0.01,
        theo=theo,
        exp=date(2026, 5, 1),
    )
    p = OptionContract.model_validate(
        p.model_dump() | {"bid": Decimal("2.0"), "ask": Decimal("2.0")}
    )
    mp = compute_mispricing([c], [p])
    assert mp is not None
    assert mp["mispricing"]["sentiment"] == "neutral"


@pytest.mark.unit
def test_mispricing_none_without_theoretical_prices() -> None:
    c = _contract_v(
        strike=100,
        side=OptionSide.CALL,
        oi=10,
        delta=0.5,
        gamma=0.01,
        theo=None,
        exp=date(2026, 5, 1),
    )
    assert compute_mispricing([c], []) is None


@pytest.mark.unit
def test_moneyness_bucketing_and_dominant() -> None:
    exp = date(2026, 6, 1)
    calls = [
        _contract_v(
            strike=100,
            side=OptionSide.CALL,
            oi=100,
            delta=0.05,
            gamma=0.01,
            exp=exp,
            vol=5000,
        ),
        _contract_v(
            strike=100,
            side=OptionSide.CALL,
            oi=50,
            delta=0.55,
            gamma=0.01,
            exp=exp,
            vol=10,
        ),
    ]
    puts = [
        _contract_v(
            strike=100,
            side=OptionSide.PUT,
            oi=10,
            delta=-0.55,
            gamma=0.01,
            exp=exp,
            vol=10,
        ),
    ]
    ms = compute_moneyness_buckets(calls, puts)["moneyness_summary"]
    assert ms["dominant_call_bucket"] == "deep_otm"
    by = {b["bucket"]: b for b in ms["buckets"]}
    assert by["deep_otm"]["call_volume"] == 5000
    assert by["atm"]["call_oi"] == 50


@pytest.mark.unit
def test_moneyness_skips_contracts_without_greeks() -> None:
    exp = date(2026, 6, 1)
    c = OptionContract.model_validate(
        _contract_v(
            strike=100,
            side=OptionSide.CALL,
            oi=1000,
            delta=0.5,
            gamma=0.01,
            exp=exp,
            vol=100,
        ).model_dump()
        | {"greeks": None}
    )
    ms = compute_moneyness_buckets([c], [])["moneyness_summary"]
    assert sum(b["call_oi"] for b in ms["buckets"]) == 0


@pytest.mark.unit
def test_pin_risk_none_when_dte_long() -> None:
    exp = date(2026, 12, 31)
    c = _contract_v(
        strike=100,
        side=OptionSide.CALL,
        oi=5000,
        delta=0.5,
        gamma=0.01,
        itm_p=Decimal("0.5"),
        exp=exp,
    )
    assert compute_pin_risk([c], [], exp.isoformat(), 100.0, date(2026, 1, 1)) is None


@pytest.mark.unit
def test_pin_risk_finds_max_strike() -> None:
    exp = date(2026, 1, 12)
    as_of = date(2026, 1, 10)
    calls = [
        _contract_v(
            strike=100,
            side=OptionSide.CALL,
            oi=5000,
            delta=0.5,
            gamma=0.01,
            itm_p=Decimal("0.5"),
            exp=exp,
            vol=100,
        ),
        _contract_v(
            strike=110,
            side=OptionSide.CALL,
            oi=2000,
            delta=0.3,
            gamma=0.01,
            itm_p=Decimal("0.1"),
            exp=exp,
            vol=100,
        ),
    ]
    pin = compute_pin_risk(calls, [], exp.isoformat(), 100.0, as_of)
    assert pin is not None
    assert pin["max_pin_strike"] == 100.0
    assert pin["dte"] == 2


@pytest.mark.unit
def test_window_near_and_mid_select_different_expirations(toy_chain: tuple) -> None:
    """Regression guard for the near/mid window collapse bug: with expiries in both
    DTE bands, near and mid must resolve to different contracts and different
    downstream signals, not the same nearest-two-expirations pick."""
    chain, near_calls, near_puts = toy_chain
    mid_exp = date(2026, 2, 18)  # ~40 DTE from TOY_AS_OF: falls in the mid band.
    mid_calls = [
        c.model_copy(
            update={
                "expiration_date": mid_exp,
                "contract_symbol": f"MID-{c.contract_symbol}",
                "strike": c.strike + Decimal("20"),
            }
        )
        for c in near_calls
    ]
    mid_puts = [
        p.model_copy(
            update={
                "expiration_date": mid_exp,
                "contract_symbol": f"MID-{p.contract_symbol}",
                "strike": p.strike + Decimal("20"),
            }
        )
        for p in near_puts
    ]
    calls = [*near_calls, *mid_calls]
    puts = [*near_puts, *mid_puts]
    combined_chain = chain.model_copy(
        update={
            "calls": calls,
            "puts": puts,
            "available_expirations": [chain.expiration_date, mid_exp],
        }
    )
    quote = {"current_price": 595.0}
    near_result = build_options_positioning(
        chain=combined_chain,
        calls=calls,
        puts=puts,
        quote=quote,
        symbol="SPY",
        window="near",
        as_of_date=TOY_AS_OF,
    )
    mid_result = build_options_positioning(
        chain=combined_chain,
        calls=calls,
        puts=puts,
        quote=quote,
        symbol="SPY",
        window="mid",
        as_of_date=TOY_AS_OF,
    )
    assert near_result.methodology.data_inputs.get(
        "expirations_used"
    ) != mid_result.methodology.data_inputs.get("expirations_used")
    assert near_result.gex_profile != mid_result.gex_profile


def test_build_options_positioning_includes_new_sections() -> None:
    exp = date(2026, 3, 20)
    calls = [
        _contract_v(strike=100, side=OptionSide.CALL, oi=100, delta=0.5, gamma=0.01, exp=exp),
    ]
    puts: list[OptionContract] = []
    chain = OptionsChain(
        underlying_symbol="Z",
        expiration_date=exp,
        available_expirations=[exp],
        underlying_price=Decimal("100"),
        calls=calls,
        puts=puts,
    )
    raw = _build_pos_dict(
        chain, calls, puts, {"current_price": 100.0}, "Z", "near", as_of_date=date(2026, 3, 1)
    )
    model = OptionsPositioningResult.model_validate(raw)
    assert model.vanna_exposure is not None
    assert model.charm_exposure is not None
    assert model.moneyness_summary is not None
    assert model.pin_risk is None
