"""Tiered narratives for deterministic instrument and report summaries."""

from __future__ import annotations

from copinance_os.data.literacy import reports as reports_lit
from copinance_os.domain.literacy import TieredCopy
from copinance_os.domain.models.profile import FinancialLiteracy

_EQ_LABEL_INSTRUMENT = TieredCopy(
    beginner="Company",
    intermediate="Instrument",
    advanced="Instrument",
)
_EQ_LABEL_SECTOR = TieredCopy(
    beginner="Business area",
    intermediate="Sector",
    advanced="Sector",
)
_EQ_LABEL_PRICE = TieredCopy(
    beginner="Current stock price",
    intermediate="Current Price",
    advanced="Spot",
)
_EQ_LABEL_TREND = TieredCopy(
    beginner="Price direction",
    intermediate="Price Trend",
    advanced="Trend",
)
_EQ_LABEL_PE = TieredCopy(
    beginner="Valuation (price vs earnings)",
    intermediate="P/E Ratio",
    advanced="P/E",
)
_EQ_LABEL_ROE = TieredCopy(
    beginner="Profitability (return on equity)",
    intermediate="ROE",
    advanced="ROE",
)

_OPTIONS_HEADER = TieredCopy(
    beginner="Options snapshot",
    intermediate="Options snapshot",
    advanced="Options snapshot",
)
_OPTIONS_EXPIRATION = TieredCopy(
    beginner="Expiration date",
    intermediate="Expiration",
    advanced="Expiry",
)
_OPTIONS_CONTRACTS = TieredCopy(
    beginner="Number of option contracts reviewed",
    intermediate="Contracts analyzed",
    advanced="Contracts analyzed",
)
_OPTIONS_UNDERLYING = TieredCopy(
    beginner="Stock price used",
    intermediate="Underlying Price",
    advanced="Underlying",
)
_OPTIONS_PC_OI = TieredCopy(
    beginner="Put/call balance (open contracts)",
    intermediate="Put/Call Open Interest Ratio",
    advanced="Put/Call OI",
)
_OPTIONS_AVG_IV = TieredCopy(
    beginner="Average expected swing (implied volatility)",
    intermediate="Average Implied Volatility",
    advanced="Avg IV",
)

_ASSESS_UPPER_RANGE = TieredCopy(
    beginner="Price is near the top of the selected range.",
    intermediate="Trading near the upper end of the selected range.",
    advanced="Spot is near the period high.",
)
_ASSESS_LOWER_RANGE = TieredCopy(
    beginner="Price is near the bottom of the selected range.",
    intermediate="Trading near the lower end of the selected range.",
    advanced="Spot is near the period low.",
)
_ASSESS_LIQ_TIGHT = TieredCopy(
    beginner="Short-term liquidity appears tight from the current ratio.",
    intermediate="Liquidity is tight based on the current ratio.",
    advanced="Current ratio indicates tight liquidity.",
)
_ASSESS_LIQ_STRONG = TieredCopy(
    beginner="Short-term liquidity appears strong from the current ratio.",
    intermediate="Liquidity looks strong based on the current ratio.",
    advanced="Current ratio indicates strong liquidity.",
)

_REPORT_INSTRUMENT_DONE = TieredCopy(
    beginner="Stock snapshot is ready.",
    intermediate="Instrument analysis completed.",
    advanced="Deterministic instrument pass completed.",
)
_REPORT_MARKET_TEMPLATE = TieredCopy(
    beginner=(
        "Market and macro snapshot for {idx}. Market indicators are {mri}; "
        "macro indicators are {macro}."
    ),
    intermediate=(
        "Deterministic market and macro regime snapshot for {idx}. "
        "Market indicators: {mri}; macro block: {macro}."
    ),
    advanced=(
        "Deterministic market/macro regime snapshot for {idx}. "
        "Market indicators: {mri}; macro block: {macro}."
    ),
)
_REPORT_QD_DONE = TieredCopy(
    beginner="Answer from the research tools is ready.",
    intermediate="Question-driven analysis completed.",
    advanced="Question-driven tool-loop analysis completed.",
)
_REPORT_QD_NO_SUMMARY = TieredCopy(
    beginner="No final narrative was available; tool results are shown instead.",
    intermediate="Final LLM narrative was not available; summary includes formatted tool output.",
    advanced="Final narrative unavailable; summary includes formatted tool output.",
)


def _pick(copy: TieredCopy, lit: FinancialLiteracy) -> str:
    return copy.pick(lit)


def equity_label_instrument(lit: FinancialLiteracy) -> str:
    return _pick(_EQ_LABEL_INSTRUMENT, lit)


def equity_label_sector(lit: FinancialLiteracy) -> str:
    return _pick(_EQ_LABEL_SECTOR, lit)


def equity_label_price(lit: FinancialLiteracy) -> str:
    return _pick(_EQ_LABEL_PRICE, lit)


def equity_label_trend(lit: FinancialLiteracy) -> str:
    return _pick(_EQ_LABEL_TREND, lit)


def equity_label_pe(lit: FinancialLiteracy) -> str:
    return _pick(_EQ_LABEL_PE, lit)


def equity_label_roe(lit: FinancialLiteracy) -> str:
    return _pick(_EQ_LABEL_ROE, lit)


def options_header(symbol: str, lit: FinancialLiteracy) -> str:
    return f"{_pick(_OPTIONS_HEADER, lit)} for {symbol}"


def options_label_expiration(lit: FinancialLiteracy) -> str:
    return _pick(_OPTIONS_EXPIRATION, lit)


def options_label_contracts(lit: FinancialLiteracy) -> str:
    return _pick(_OPTIONS_CONTRACTS, lit)


def options_label_underlying(lit: FinancialLiteracy) -> str:
    return _pick(_OPTIONS_UNDERLYING, lit)


def options_label_put_call_oi(lit: FinancialLiteracy) -> str:
    return _pick(_OPTIONS_PC_OI, lit)


def options_label_avg_iv(lit: FinancialLiteracy) -> str:
    return _pick(_OPTIONS_AVG_IV, lit)


def assessment_upper_range(lit: FinancialLiteracy) -> str:
    return _pick(_ASSESS_UPPER_RANGE, lit)


def assessment_lower_range(lit: FinancialLiteracy) -> str:
    return _pick(_ASSESS_LOWER_RANGE, lit)


def assessment_liquidity_tight(lit: FinancialLiteracy) -> str:
    return _pick(_ASSESS_LIQ_TIGHT, lit)


def assessment_liquidity_strong(lit: FinancialLiteracy) -> str:
    return _pick(_ASSESS_LIQ_STRONG, lit)


def report_instrument_default_summary(lit: FinancialLiteracy) -> str:
    return _pick(_REPORT_INSTRUMENT_DONE, lit)


def report_market_summary(idx: str, mri_ok: bool, macro_ok: bool, lit: FinancialLiteracy) -> str:
    return _pick(_REPORT_MARKET_TEMPLATE, lit).format(
        idx=idx,
        mri="ok" if mri_ok else "incomplete",
        macro="ok" if macro_ok else "incomplete",
    )


def report_question_driven_default(lit: FinancialLiteracy) -> str:
    return _pick(_REPORT_QD_DONE, lit)


def report_question_driven_partial_limitation(lit: FinancialLiteracy) -> str:
    return _pick(_REPORT_QD_NO_SUMMARY, lit)


def report_assumptions(lit: FinancialLiteracy) -> tuple[str, str]:
    return reports_lit.report_assumptions(lit)


def report_limitations(lit: FinancialLiteracy) -> tuple[str, str]:
    return reports_lit.report_limitations(lit)
