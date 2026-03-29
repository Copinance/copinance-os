"""Shared helpers for the market CLI (formatting chains, history rows, fundamentals tables)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from rich.table import Table

from copinance_os.domain.models.market import MarketDataPoint, OptionsChain, OptionSide
from copinance_os.interfaces.cli.shared.formatting import format_compact_number

SUPPORTED_HISTORY_INTERVALS = ("1d", "1wk", "1mo", "1h", "5m", "15m", "30m", "60m")


def history_rows_from_provider(history: list[Any]) -> list[dict[str, Any]]:
    """Convert list of MarketDataPoint to list of dicts for display/cache."""
    rows: list[dict[str, Any]] = []
    for point in history:
        if isinstance(point, MarketDataPoint):
            rows.append(
                {
                    "timestamp": point.timestamp.isoformat(),
                    "open_price": str(point.open_price),
                    "close_price": str(point.close_price),
                    "high_price": str(point.high_price),
                    "low_price": str(point.low_price),
                    "volume": point.volume,
                }
            )
        else:
            rows.append(dict(point))
    return rows


def contract_greeks_for_display(contract: Any) -> dict[str, Any | None]:
    """Extract optional BSM Greeks for CLI display (``OptionContract`` or cached dict).

    Cached payloads use ``model_dump(mode="json")`` (decimals as strings, nested ``greeks``).
    """
    g = contract.get("greeks") if isinstance(contract, dict) else getattr(contract, "greeks", None)
    if g is None:
        return dict.fromkeys(("delta", "gamma", "theta", "vega", "rho"))
    if isinstance(g, dict):
        return {
            "delta": g.get("delta"),
            "gamma": g.get("gamma"),
            "theta": g.get("theta"),
            "vega": g.get("vega"),
            "rho": g.get("rho"),
        }
    return {
        "delta": getattr(g, "delta", None),
        "gamma": getattr(g, "gamma", None),
        "theta": getattr(g, "theta", None),
        "vega": getattr(g, "vega", None),
        "rho": getattr(g, "rho", None),
    }


def fmt_optional_greek(value: Any) -> str:
    """Format BSM sensitivities for TTY: avoid `-1.1102…` noise where Delta is ~0."""
    if value is None:
        return "-"
    try:
        x = float(value) if isinstance(value, (Decimal, int, float)) else float(str(value))
    except (TypeError, ValueError, OverflowError):
        return str(value)
    if x != x:  # NaN
        return "-"
    ax = abs(x)
    if ax < 1e-10:
        return "0"
    if ax < 1e-4:
        return f"{x:.2e}"
    return f"{x:.4f}"


def options_chain_to_display(
    option_side: OptionSide,
    options_chain: Any,
) -> tuple[str, str, list[dict[str, Any]]]:
    """Return (underlying_price_str, expiration_str, list of contract dicts) for display."""

    if isinstance(options_chain, OptionsChain):
        underlying_price = (
            str(options_chain.underlying_price)
            if options_chain.underlying_price is not None
            else "N/A"
        )
        exp_str = (
            options_chain.expiration_date.isoformat()
            if options_chain.expiration_date is not None
            else "N/A"
        )
        if option_side == OptionSide.CALL:
            raw = options_chain.calls
        elif option_side == OptionSide.PUT:
            raw = options_chain.puts
        else:
            calls_legs, puts_legs = options_chain.calls, options_chain.puts
            raw = (
                [x for pair in zip(calls_legs, puts_legs, strict=False) for x in pair]
                + calls_legs[len(puts_legs) :]
                + puts_legs[len(calls_legs) :]
            )
        contracts: list[dict[str, Any]] = []
        for oc in raw:
            row: dict[str, Any] = {
                "contract_symbol": oc.contract_symbol,
                "side": oc.side.value,
                "strike": oc.strike,
                "last_price": oc.last_price,
                "implied_volatility": oc.implied_volatility,
                "open_interest": oc.open_interest,
                "volume": oc.volume,
            }
            row.update(contract_greeks_for_display(oc))
            contracts.append(row)
        return underlying_price, exp_str, contracts
    data = options_chain
    underlying_price = str(data.get("underlying_price", "N/A") or "N/A")
    exp = data.get("expiration_date")
    exp_str = exp if isinstance(exp, str) else (exp.isoformat() if exp else "N/A")
    calls_list: list[dict[str, Any]] = data.get("calls") or []
    puts_list: list[dict[str, Any]] = data.get("puts") or []
    if option_side == OptionSide.CALL:
        raw_contracts: list[dict[str, Any]] = calls_list
    elif option_side == OptionSide.PUT:
        raw_contracts = puts_list
    else:
        raw_contracts = (
            [x for pair in zip(calls_list, puts_list, strict=False) for x in pair]
            + calls_list[len(puts_list) :]
            + puts_list[len(calls_list) :]
        )
    cache_contracts: list[dict[str, Any]] = []
    for row_dict in raw_contracts:
        row = {
            "contract_symbol": row_dict.get("contract_symbol", ""),
            "side": row_dict.get("side", ""),
            "strike": row_dict.get("strike"),
            "last_price": row_dict.get("last_price"),
            "implied_volatility": row_dict.get("implied_volatility"),
            "open_interest": row_dict.get("open_interest"),
            "volume": row_dict.get("volume"),
        }
        row.update(contract_greeks_for_display(row_dict))
        cache_contracts.append(row)
    return underlying_price, exp_str, cache_contracts


def format_fundamentals_value(value: Any) -> str:
    """Format a value for fundamentals display."""
    if value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


def income_trend_table(income_statements: list[dict[str, Any]], period_type: str) -> Table | None:
    """Build a compact income trend table (revenue, net income, EPS) for the last 5 periods."""
    if not income_statements:
        return None
    rows = []
    for st in income_statements[:5]:
        period = st.get("period") or {}
        fy = period.get("fiscal_year") or "—"
        rev = st.get("total_revenue")
        ni = st.get("net_income")
        eps = st.get("diluted_eps") or st.get("earnings_per_share")
        if rev is None and ni is None:
            continue
        rev_str = format_compact_number(rev) if rev is not None else "—"
        ni_str = format_compact_number(ni) if ni is not None else "—"
        eps_str = f"{float(eps):.2f}" if eps is not None else "—"
        rows.append((str(fy), rev_str, ni_str, eps_str))
    if not rows:
        return None
    table = Table(title=f"Income trend ({period_type})")
    table.add_column("Fiscal year", style="cyan")
    table.add_column("Revenue", justify="right", style="green")
    table.add_column("Net income", justify="right", style="green")
    table.add_column("EPS", justify="right", style="magenta")
    for r in rows:
        table.add_row(*r)
    return table
