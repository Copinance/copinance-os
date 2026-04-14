"""Integration tests: options positioning + QuantLib BSM on real Yahoo-style data.

Two layers:

1. **Snapshot (default CI)** — committed SPY chain JSON from yfinance; deterministic
   ``as_of_date`` in fixture metadata. Validates end-to-end positioning, enrich path,
   and analytical cross-checks (delta/NPV/parity).

2. **Live wire (optional)** — fetches current SPY chain; skipped when Yahoo/yfinance is
   unreachable (same pattern as fundamentals integration tests).

These checks are *sanity / consistency* backtests (model vs itself and loose parity),
not trading P&L backtests (which would need historical chains and realized paths).
"""

from __future__ import annotations

import json
import math
import statistics
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from copinance_os.data.analytics.options.greeks import (
    DEFAULT_RISK_FREE_RATE,
    compute_european_bsm_greeks,
    enrich_options_chain_missing_greeks,
)
from copinance_os.data.analytics.options.positioning import build_options_positioning
from copinance_os.data.providers.yfinance import YFinanceMarketProvider
from copinance_os.domain.models.market import OptionContract, OptionsChain, OptionSide

pytest.importorskip("QuantLib")

_FIXTURE = (
    Path(__file__).resolve().parents[5]
    / "fixtures"
    / "options_integration"
    / "spy_chain_snapshot.json"
)


def _maybe_skip_yfinance_transient_error(exc: BaseException) -> None:
    if isinstance(exc, (ValueError, OSError, ConnectionError)):
        msg = str(exc)
        if "Failed to fetch" in msg or "Connection" in msg or "curl" in msg:
            pytest.skip(f"Network unavailable or transient error: {exc}")


def _contract_mid(c: OptionContract) -> float:
    bid = float(c.bid or 0)
    ask = float(c.ask or 0)
    if bid > 0 or ask > 0:
        mid = (bid + ask) / 2.0 if ask >= bid else max(bid, ask)
        return float(mid)
    return float(c.last_price or 0)


def _load_snapshot_chain() -> tuple[OptionsChain, date]:
    raw = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    snap = raw.get("metadata", {}).get("snapshot_as_of")
    if not snap:
        pytest.fail("fixture missing metadata.snapshot_as_of")
    as_of = date.fromisoformat(str(snap))
    chain = OptionsChain.model_validate(raw)
    return chain, as_of


def _year_fraction(as_of: date, exp: date) -> float:
    return max(1e-8, (exp - as_of).days / 365.0)


@pytest.mark.integration
class TestOptionsPositioningSnapshotIntegration:
    """Deterministic checks on a frozen real-market-shaped SPY chain."""

    def test_fixture_loads_and_positioning_validates(self) -> None:
        chain, as_of = _load_snapshot_chain()
        calls = list(chain.calls or [])
        puts = list(chain.puts or [])
        assert calls and puts
        spot = float(chain.underlying_price or 0)
        assert spot > 100.0

        quote = {"current_price": spot}
        model = build_options_positioning(
            chain=chain,
            calls=calls,
            puts=puts,
            quote=quote,
            symbol=chain.underlying_symbol,
            window="near",
            as_of_date=as_of,
            enrich_missing_greeks=True,
        )
        assert model.symbol == "SPY"
        assert model.window == "near"
        assert model.data_quality is not None and model.data_quality > 0.3
        assert model.delta_exposure is not None
        assert model.vanna_exposure is not None
        assert model.charm_exposure is not None
        assert model.moneyness_summary is not None
        assert model.iv_metrics is not None
        assert model.signal_categories is not None
        assert model.regime in ("positive_gamma", "negative_gamma", "neutral")
        spec_ids = {s.id for s in model.methodology.specs}
        assert "options.positioning.bias" in spec_ids
        assert "options.greeks.quantlib_bsm_european" in spec_ids

    def test_enriched_greeks_self_consistent_with_recompute(self) -> None:
        chain, as_of = _load_snapshot_chain()
        c2 = chain.model_copy(
            update={"calls": list(chain.calls or []), "puts": list(chain.puts or [])}
        )
        enriched = enrich_options_chain_missing_greeks(c2, evaluation_date=as_of)
        spot = enriched.underlying_price
        assert spot is not None
        for c in (*enriched.calls, *enriched.puts):
            assert c.greeks is not None
            g = c.greeks
            assert g.theoretical_price is not None
            assert g.itm_probability is not None
            assert 0.0 <= float(g.itm_probability) <= 1.0
            assert g.vanna is not None and g.charm is not None and g.volga is not None
            if c.side == OptionSide.CALL:
                assert 0.0 <= float(g.delta) <= 1.0
            else:
                assert -1.0 <= float(g.delta) <= 0.0

            ref = compute_european_bsm_greeks(
                spot=spot,
                strike=c.strike,
                risk_free_rate=DEFAULT_RISK_FREE_RATE,
                dividend_yield=Decimal("0"),
                implied_volatility=c.implied_volatility or Decimal("0"),
                expiration_date=c.expiration_date,
                evaluation_date=as_of,
                side=c.side,
            )
            assert ref is not None
            assert abs(float(g.delta) - float(ref.delta)) < 1e-5
            assert abs(float(g.theoretical_price) - float(ref.theoretical_price)) < 5e-3

    def test_npv_vs_mid_median_reasonable(self) -> None:
        """Loose 'backtest': mid vs BSM NPV at quoted IV should not be wildly off on average."""
        chain, as_of = _load_snapshot_chain()
        enriched = enrich_options_chain_missing_greeks(
            chain.model_copy(
                update={"calls": list(chain.calls or []), "puts": list(chain.puts or [])}
            ),
            evaluation_date=as_of,
        )
        spot = enriched.underlying_price
        assert spot is not None
        rel_errors: list[float] = []
        for c in (*enriched.calls, *enriched.puts):
            if c.greeks is None or c.greeks.theoretical_price is None:
                continue
            mid = _contract_mid(c)
            theo = float(c.greeks.theoretical_price)
            if mid <= 0 or theo <= 0:
                continue
            if c.implied_volatility is None or float(c.implied_volatility) <= 0:
                continue
            rel_errors.append(abs(mid - theo) / max(0.01, theo))
        assert len(rel_errors) >= 8
        med = float(statistics.median(rel_errors))
        assert med < 0.35, f"median |mid-NPV|/NPV too large: {med}"

    def test_put_call_parity_atm_band(self) -> None:
        chain, as_of = _load_snapshot_chain()
        spot = float(chain.underlying_price or 0)
        exp = chain.expiration_date
        t_year = _year_fraction(as_of, exp)
        r = float(DEFAULT_RISK_FREE_RATE)
        q = 0.0

        by_strike: dict[float, dict[str, OptionContract]] = {}
        for c in chain.calls or []:
            by_strike.setdefault(float(c.strike), {})["call"] = c
        for p in chain.puts or []:
            by_strike.setdefault(float(p.strike), {})["put"] = p

        errs: list[float] = []
        for k, legs in by_strike.items():
            call = legs.get("call")
            put = legs.get("put")
            if call is None or put is None:
                continue
            cm = _contract_mid(call)
            pm = _contract_mid(put)
            if cm <= 0 or pm <= 0:
                continue
            lhs = cm - pm
            rhs = spot * math.exp(-q * t_year) - k * math.exp(-r * t_year)
            errs.append(abs(lhs - rhs) / spot)
        assert errs, "no paired strikes with mids for parity check"
        assert min(errs) < 0.04, f"best ATM parity error vs spot too large: {min(errs)}"

    def test_pin_risk_when_dte_within_window(self) -> None:
        chain, as_of = _load_snapshot_chain()
        dte = (chain.expiration_date - as_of).days
        assert 1 <= dte <= 5, "fixture should keep DTE in 1..5 for pin-risk coverage"
        raw = build_options_positioning(
            chain=chain,
            calls=list(chain.calls or []),
            puts=list(chain.puts or []),
            quote={"current_price": float(chain.underlying_price or 0)},
            symbol="SPY",
            window="near",
            as_of_date=as_of,
            enrich_missing_greeks=True,
        ).model_dump(mode="python")
        pr = raw.get("pin_risk")
        assert pr is not None
        assert pr["pin_risk_level"] in ("low", "moderate", "high")
        assert pr["dte"] == dte


@pytest.mark.integration
class TestYFinanceOptionsPositioningLiveIntegration:
    """Live Yahoo chain → positioning (skipped when the wire fails)."""

    @pytest.mark.asyncio
    async def test_live_spy_chain_positioning_smoke(self) -> None:
        provider = YFinanceMarketProvider()
        try:
            chain = await provider.get_options_chain("SPY", None)
        except (ValueError, OSError, ConnectionError) as e:
            _maybe_skip_yfinance_transient_error(e)
            raise
        calls = list(chain.calls or [])
        puts = list(chain.puts or [])
        if len(calls) < 5 or len(puts) < 5:
            pytest.skip("insufficient SPY options rows from provider")
        spot = float(chain.underlying_price or 0)
        if spot <= 0:
            pytest.skip("no underlying price on live chain")

        as_of = date.today()
        model = build_options_positioning(
            chain=chain,
            calls=calls,
            puts=puts,
            quote={"current_price": spot},
            symbol="SPY",
            window="near",
            as_of_date=as_of,
            enrich_missing_greeks=True,
        )
        assert model.delta_exposure is not None
        assert model.gex_profile is not None
        assert model.vanna_exposure is not None
