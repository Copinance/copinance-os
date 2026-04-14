from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import ModuleType
from typing import Any

import pytest

from copinance_os.data.analytics.options.positioning import build_options_positioning
from copinance_os.data.literacy import instrument_analysis as ia_lit
from copinance_os.data.literacy import macro_indicators as macro_lit
from copinance_os.data.literacy import market_regime as mr_lit
from copinance_os.data.literacy import options_positioning as op_lit
from copinance_os.data.literacy import reports as reports_lit
from copinance_os.domain.literacy import TieredCopy
from copinance_os.domain.models.market import OptionContract, OptionGreeks, OptionsChain, OptionSide
from copinance_os.domain.models.profile import FinancialLiteracy

_DEGENERATE_ALLOWLIST = {
    ("copinance_os.data.literacy.market_regime", "_VIX_SENTIMENT"),
    ("copinance_os.data.literacy.instrument_analysis", "_OPTIONS_HEADER"),
    ("copinance_os.data.literacy.instrument_analysis", "_OPTIONS_NOTE"),
    ("copinance_os.data.literacy.instrument_analysis", "_BOOL_YES"),
    ("copinance_os.data.literacy.instrument_analysis", "_BOOL_NO"),
}
_BEGINNER_DENYLIST = (
    "ROE",
    "ROIC",
    "ROA",
    "EPS",
    "P/E",
    "P/B",
    "EV",
    "EBITDA",
    "FCF",
    "WACC",
    "DTE",
    "GEX",
    "IV",
    "OI",
    "P/C",
    "ATM",
    "OTM",
    "ITM",
    "BSM",
    "RSI",
    "MACD",
    "MA",
    "VIX",
    "FRED",
)
_EXPANSION_HINTS: dict[str, tuple[str, ...]] = {
    "ROE": ("return on equity",),
    "EPS": ("earnings per share",),
    "P/E": ("price to earnings", "price vs earnings"),
    "P/B": ("price to book",),
    "EV": ("enterprise value",),
    "EBITDA": ("earnings before interest, taxes, depreciation, and amortization",),
    "FCF": ("free cash flow",),
    "WACC": ("weighted average cost of capital",),
    "DTE": ("days to expiry", "days to expiration"),
    "GEX": ("gamma exposure",),
    "IV": ("implied volatility", "expected swing"),
    "OI": ("open interest", "open contracts"),
    "P/C": ("put/call",),
    "ATM": ("at the money",),
    "OTM": ("out of the money",),
    "ITM": ("in the money",),
    "BSM": ("black-scholes", "black scholes"),
    "RSI": ("relative strength index",),
    "MACD": ("moving average convergence divergence",),
    "MA": ("moving average",),
    "VIX": ("volatility index",),
    "FRED": ("federal reserve economic data",),
}


def _walk_tiered_copy(value: object) -> list[TieredCopy]:
    if isinstance(value, TieredCopy):
        return [value]
    if isinstance(value, dict):
        out: list[TieredCopy] = []
        for item in value.values():
            out.extend(_walk_tiered_copy(item))
        return out
    if isinstance(value, (list, tuple, set)):
        out: list[TieredCopy] = []
        for item in value:
            out.extend(_walk_tiered_copy(item))
        return out
    return []


def _module_tiered_copies(module: ModuleType) -> list[tuple[str, TieredCopy]]:
    out: list[tuple[str, TieredCopy]] = []
    for name, val in vars(module).items():
        if name.startswith("__"):
            continue
        for tc in _walk_tiered_copy(val):
            out.append((name, tc))
    return out


def _find_unexpanded_acronyms(text: str) -> list[str]:
    lowered = text.lower()
    hits: list[str] = []
    for acronym in _BEGINNER_DENYLIST:
        start = 0
        while True:
            idx = text.find(acronym, start)
            if idx == -1:
                break
            prefix = lowered[max(0, idx - 40) : idx + len(acronym)]
            hints = _EXPANSION_HINTS.get(acronym, ())
            if not any(hint in prefix for hint in hints):
                hits.append(acronym)
                break
            start = idx + len(acronym)
    return hits


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
        implied_volatility=Decimal(str(iv / 100.0 if iv > 2 else iv)),
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
        implied_volatility=Decimal(str(iv / 100.0 if iv > 2 else iv)),
        greeks=OptionGreeks(
            delta=Decimal(str(delta)),
            gamma=Decimal(str(gamma)),
            theta=Decimal("0"),
            vega=Decimal("0"),
            rho=Decimal("0"),
        ),
    )


def _collect_numbers(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: _collect_numbers(v)
            for k, v in value.items()
            if isinstance(v, (dict, list, int, float))
        }
    if isinstance(value, list):
        return [_collect_numbers(v) for v in value if isinstance(v, (dict, list, int, float))]
    return value


@pytest.mark.unit
def test_beginner_copy_avoids_acronym_leaks() -> None:
    modules = (ia_lit, op_lit, macro_lit, mr_lit, reports_lit)
    leaks: list[str] = []
    for module in modules:
        for symbol_name, tc in _module_tiered_copies(module):
            beginner_text = tc.pick(FinancialLiteracy.BEGINNER)
            offending = _find_unexpanded_acronyms(beginner_text)
            if offending:
                leaks.append(f"{module.__name__}:{symbol_name}:{offending}")
    assert not leaks


@pytest.mark.unit
def test_tiered_copy_not_degenerate_except_allowlisted() -> None:
    modules = (ia_lit, op_lit, macro_lit, mr_lit, reports_lit)
    for module in modules:
        for symbol_name, tc in _module_tiered_copies(module):
            if (
                module.__name__,
                symbol_name,
            ) in _DEGENERATE_ALLOWLIST:
                continue
            rendered = {
                tc.pick(FinancialLiteracy.BEGINNER),
                tc.pick(FinancialLiteracy.INTERMEDIATE),
                tc.pick(FinancialLiteracy.ADVANCED),
            }
            assert len(rendered) >= 2, f"Degenerate TieredCopy at {module.__name__}:{symbol_name}"


@pytest.mark.unit
def test_numeric_payload_is_identical_across_literacy_tiers() -> None:
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
        expiration_date=date(2026, 1, 16),
        available_expirations=[date(2026, 1, 16)],
        underlying_price=Decimal("595"),
        calls=calls,
        puts=puts,
    )
    b = build_options_positioning(
        chain=chain,
        calls=calls,
        puts=puts,
        quote={"current_price": 595.0},
        symbol="SPY",
        window="near",
        as_of_date=date(2026, 1, 9),
        financial_literacy=FinancialLiteracy.BEGINNER,
    ).model_dump(mode="json")
    i = build_options_positioning(
        chain=chain,
        calls=calls,
        puts=puts,
        quote={"current_price": 595.0},
        symbol="SPY",
        window="near",
        as_of_date=date(2026, 1, 9),
        financial_literacy=FinancialLiteracy.INTERMEDIATE,
    ).model_dump(mode="json")
    a = build_options_positioning(
        chain=chain,
        calls=calls,
        puts=puts,
        quote={"current_price": 595.0},
        symbol="SPY",
        window="near",
        as_of_date=date(2026, 1, 9),
        financial_literacy=FinancialLiteracy.ADVANCED,
    ).model_dump(mode="json")
    assert _collect_numbers(b) == _collect_numbers(i)
    assert _collect_numbers(b) == _collect_numbers(a)
