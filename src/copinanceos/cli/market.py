"""Market data CLI commands."""

from __future__ import annotations

import contextlib
from datetime import datetime
from decimal import Decimal
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from copinanceos.application.use_cases.fundamentals import GetStockFundamentalsRequest
from copinanceos.application.use_cases.market import (
    GetHistoricalDataRequest,
    GetOptionsChainRequest,
    GetQuoteRequest,
    InstrumentSearchMode,
    SearchInstrumentsRequest,
)
from copinanceos.cli.error_handler import handle_cli_error
from copinanceos.cli.formatting import (
    format_compact_number,
    format_exchange,
    format_price,
    format_volume,
)
from copinanceos.cli.utils import async_command
from copinanceos.domain.models.market import MarketDataPoint, OptionsChain, OptionSide
from copinanceos.infrastructure.config import get_storage_path_safe
from copinanceos.infrastructure.containers import container
from copinanceos.infrastructure.persistence import get_cache_dir

market_app = typer.Typer(
    help="Market data: search, quote, history, options (BSM Greeks via QuantLib), fundamentals",
)
console = Console()
SUPPORTED_HISTORY_INTERVALS = ("1d", "1wk", "1mo", "1h", "5m", "15m", "30m", "60m")


@market_app.command("search")
@async_command
async def search_instruments(
    query: str = typer.Argument(..., help="Search query (symbol or display name)"),
    limit: int = typer.Option(10, help="Maximum results"),
    search_mode: InstrumentSearchMode = typer.Option(
        InstrumentSearchMode.AUTO,
        "--mode",
        help="Search mode: auto, symbol, or general",
    ),
) -> None:
    """Search for market instruments by symbol or name."""
    use_case = container.search_instruments_use_case()
    request = SearchInstrumentsRequest(query=query, limit=limit, search_mode=search_mode)
    response = await use_case.execute(request)

    if not response.instruments:
        console.print(f"No instruments found for '{query}'.", style="yellow")
        return

    table = Table(title=f"Search Results for '{query}'")
    table.add_column("Symbol", style="cyan")
    table.add_column("Name", style="magenta")
    table.add_column("Market", style="green")

    for instrument in response.instruments:
        market = format_exchange(instrument.exchange) or instrument.exchange or "—"
        table.add_row(instrument.symbol, instrument.name, market)

    console.print(table)


@market_app.command("quote")
@async_command
async def get_market_quote(
    symbol: str = typer.Argument(..., help="Instrument symbol"),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Bypass cache and fetch fresh data",
    ),
) -> None:
    """Fetch the latest market quote for an instrument."""
    symbol_upper = symbol.upper()
    cache_manager = container.cache_manager()
    quote: dict[str, Any] | None = None

    if not no_cache:
        try:
            entry = await cache_manager.get("get_market_quote", symbol=symbol_upper)
            if entry and entry.data:
                quote = dict(entry.data)
        except Exception:
            pass

    if quote is None:
        try:
            use_case = container.get_quote_use_case()
            response = await use_case.execute(GetQuoteRequest(symbol=symbol_upper))
            quote = response.quote
        except Exception as e:
            handle_cli_error(e, context={"symbol": symbol, "feature": "quote"})
            return

        if not no_cache:
            with contextlib.suppress(Exception):
                await cache_manager.set(
                    "get_market_quote",
                    data=quote,
                    metadata={"symbol": symbol_upper},
                    symbol=symbol_upper,
                )

    table = Table(title=f"Market Quote for {quote.get('symbol', symbol_upper)}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="green")

    rows = [
        ("Current Price", quote.get("current_price", "N/A")),
        ("Previous Close", quote.get("previous_close", "N/A")),
        ("Open", quote.get("open", "N/A")),
        ("High", quote.get("high", "N/A")),
        ("Low", quote.get("low", "N/A")),
        ("Volume", quote.get("volume", "N/A")),
        ("Market Cap", quote.get("market_cap", "N/A")),
        ("Currency", quote.get("currency", "N/A")),
        ("Exchange", quote.get("exchange", "N/A")),
        ("Timestamp", quote.get("timestamp", "N/A")),
    ]
    for field, value in rows:
        table.add_row(field, str(value))

    console.print(table)


def _history_rows_from_provider(history: list[Any]) -> list[dict[str, Any]]:
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


@market_app.command("history")
@async_command
async def get_market_history(
    symbol: str = typer.Argument(..., help="Instrument symbol"),
    start_date: str = typer.Option(..., "--start", help="Start date in YYYY-MM-DD format"),
    end_date: str = typer.Option(..., "--end", help="End date in YYYY-MM-DD format"),
    interval: str = typer.Option("1d", help="Data interval"),
    limit: int = typer.Option(
        0,
        "--limit",
        "-n",
        help="Maximum rows to display (0 = show all)",
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Bypass cache and fetch fresh data",
    ),
) -> None:
    """Fetch historical market data for an instrument.

    Uses the same cache as in question-driven analysis; repeated requests for the same
    symbol/range/interval are served from cache until expiry or cache clear.
    """
    if interval not in SUPPORTED_HISTORY_INTERVALS:
        handle_cli_error(
            ValueError(
                f"Unsupported interval '{interval}'. Expected one of: {', '.join(SUPPORTED_HISTORY_INTERVALS)}"
            ),
            context={"symbol": symbol, "feature": "history"},
        )
        return

    try:
        parsed_start_date = datetime.fromisoformat(start_date)
        parsed_end_date = datetime.fromisoformat(end_date)
    except ValueError as e:
        handle_cli_error(e, context={"symbol": symbol, "feature": "history"})
        return

    start_str = parsed_start_date.strftime("%Y-%m-%d")
    end_str = parsed_end_date.strftime("%Y-%m-%d")
    symbol_upper = symbol.upper()
    cache_manager = container.cache_manager()

    rows: list[dict[str, Any]] = []
    cache_file_path: str | None = None

    if not no_cache:
        try:
            entry = await cache_manager.get(
                "get_historical_market_data",
                symbol=symbol_upper,
                start_date=start_str,
                end_date=end_str,
                interval=interval,
            )
            if entry and entry.data:
                rows = list(entry.data)
                cache_file_path = entry.metadata.get("cache_file_path") if entry.metadata else None
        except Exception:
            pass

    if not rows:
        try:
            use_case = container.get_historical_data_use_case()
            response = await use_case.execute(
                GetHistoricalDataRequest(
                    symbol=symbol_upper,
                    start_date=parsed_start_date,
                    end_date=parsed_end_date,
                    interval=interval,
                )
            )
            history = response.data
        except Exception as e:
            handle_cli_error(e, context={"symbol": symbol, "feature": "history"})
            return

        if not history:
            console.print("No historical market data found", style="yellow")
            return

        rows = _history_rows_from_provider(history)
        with contextlib.suppress(Exception):
            await cache_manager.set(
                "get_historical_market_data",
                data=rows,
                metadata={"symbol": symbol_upper, "interval": interval},
                symbol=symbol_upper,
                start_date=start_str,
                end_date=end_str,
                interval=interval,
            )

    cache_dir = get_cache_dir(get_storage_path_safe())
    cache_location = cache_file_path if cache_file_path else str(cache_dir)
    console.print(f"[dim]Cache: {cache_location}[/dim]\n")

    to_show = rows[:limit] if limit else rows
    table = Table(title=f"Historical Data for {symbol_upper} ({interval})")
    table.add_column("Timestamp", style="cyan")
    table.add_column("Open", justify="right")
    table.add_column("Close", justify="right")
    table.add_column("High", justify="right")
    table.add_column("Low", justify="right")
    table.add_column("Volume", justify="right")

    for row in to_show:
        table.add_row(
            row.get("timestamp", ""),
            format_price(row.get("open_price")),
            format_price(row.get("close_price")),
            format_price(row.get("high_price")),
            format_price(row.get("low_price")),
            format_volume(row.get("volume")),
        )

    console.print(table)
    if limit and len(rows) > limit:
        console.print(
            f"[dim](showing {limit} of {len(rows)} rows; use --limit 0 to show all)[/dim]"
        )


def _contract_greeks_for_display(contract: Any) -> dict[str, Any | None]:
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


def _fmt_optional_greek(value: Any) -> str:
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


def _options_chain_to_display(
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
            # Interleave calls and puts so a small limit shows both sides
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
            row.update(_contract_greeks_for_display(oc))
            contracts.append(row)
        return underlying_price, exp_str, contracts
    # From cache: dict with calls, puts, underlying_price, expiration_date
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
        row.update(_contract_greeks_for_display(row_dict))
        cache_contracts.append(row)
    return underlying_price, exp_str, cache_contracts


@market_app.command("options")
@async_command
async def get_options_chain(
    underlying_symbol: str = typer.Argument(..., help="Underlying symbol (e.g. AAPL, SPY)"),
    expiration_date: str | None = typer.Option(
        None,
        "--expiration",
        "-e",
        help="Expiration in YYYY-MM-DD (default: earliest listed expiry on or after today)",
    ),
    option_side: OptionSide = typer.Option(
        OptionSide.ALL,
        "--side",
        "-s",
        help="call, put, or all (all = interleaved calls/puts for a compact view)",
    ),
    limit: int = typer.Option(
        0,
        "--limit",
        "-n",
        help="Maximum contracts to show (0 = show all)",
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Bypass cache (use after upgrades or when Greeks are missing from cached rows)",
    ),
    no_greeks: bool = typer.Option(
        False,
        "--no-greeks",
        help="Hide Delta/Gamma/Theta/Vega/Rho columns (default: show with '-' if unavailable)",
    ),
) -> None:
    """Fetch an options chain and show BSM Greek columns when available (QuantLib).

    The default stack estimates analytic European Greeks (delta, gamma, theta, vega, rho)
    per contract when the chain has an underlying price and each row has implied
    volatility. Requires the QuantLib Python package. Tune risk-free rate and default
    dividend yield via ``COPINANCEOS_OPTION_GREEKS_*`` (see docs: Configuration).

    Greek columns are shown by default; values appear as '-' when not computed. Cached
    chains saved before Greek support may omit them until you pass ``--no-cache``.

    Uses the same cache as question-driven analysis for identical underlying/expiration keys.
    """
    symbol_upper = underlying_symbol.upper()
    cache_manager = container.cache_manager()
    options_data: OptionsChain | dict[str, Any] | None = None

    if not no_cache:
        try:
            entry = await cache_manager.get(
                "get_options_chain",
                underlying_symbol=symbol_upper,
                expiration_date=expiration_date,
            )
            if entry and entry.data:
                options_data = dict(entry.data)
        except Exception:
            pass

    if options_data is None:
        try:
            use_case = container.get_options_chain_use_case()
            response = await use_case.execute(
                GetOptionsChainRequest(
                    underlying_symbol=symbol_upper,
                    expiration_date=expiration_date,
                )
            )
            options_data = response.chain
        except Exception as e:
            handle_cli_error(
                e, context={"underlying_symbol": underlying_symbol, "feature": "options"}
            )
            return

        chain = options_data
        if not no_cache and isinstance(chain, OptionsChain):
            try:
                # JSON-serializable dict for cache (matches tool format)
                payload = chain.model_dump(mode="json")
                await cache_manager.set(
                    "get_options_chain",
                    data=payload,
                    metadata={
                        "underlying_symbol": symbol_upper,
                        "expiration_date": expiration_date,
                    },
                    underlying_symbol=symbol_upper,
                    expiration_date=expiration_date,
                )
            except Exception:
                pass

    underlying_price, exp_str, contracts = _options_chain_to_display(option_side, options_data)
    sym = (
        options_data.underlying_symbol
        if hasattr(options_data, "underlying_symbol")
        else options_data.get("underlying_symbol", symbol_upper)
    )
    console.print(
        f"[bold]Options chain for {sym}[/bold] "
        f"(expiration: {exp_str}, underlying: {underlying_price})"
    )

    if not contracts:
        console.print("No contracts available", style="yellow")
        return

    show_greeks_columns = not no_greeks
    any_greeks = any(c.get("delta") is not None for c in contracts)
    if show_greeks_columns and not any_greeks:
        console.print(
            "[dim]Greeks: none on this snapshot (expired expiry vs today, missing spot/IV, "
            "or QuantLib). Default expiry is the first listed date on or after today; "
            "override with [bold]-e YYYY-MM-DD[/bold]. Refresh with [bold]--no-cache[/bold].[/dim]"
        )

    table = Table(title=f"{option_side.value.capitalize()} contracts")
    table.add_column("Contract", style="cyan")
    table.add_column("Side", style="magenta")
    table.add_column("Strike", justify="right")
    table.add_column("Last", justify="right")
    table.add_column("IV", justify="right")
    table.add_column("OI", justify="right")
    table.add_column("Vol", justify="right")

    if show_greeks_columns:
        table.add_column("Delta", justify="right", style="dim")
        table.add_column("Gamma", justify="right", style="dim")
        table.add_column("Theta", justify="right", style="dim")
        table.add_column("Vega", justify="right", style="dim")
        table.add_column("Rho", justify="right", style="dim")

    to_show = contracts[:limit] if limit else contracts
    for c in to_show:
        row_cells: list[str] = [
            c["contract_symbol"],
            c["side"],
            str(c["strike"]),
            str(c["last_price"]) if c.get("last_price") is not None else "-",
            str(c["implied_volatility"]) if c.get("implied_volatility") is not None else "-",
            str(c["open_interest"]) if c.get("open_interest") is not None else "-",
            str(c["volume"]) if c.get("volume") is not None else "-",
        ]
        if show_greeks_columns:
            row_cells.extend(
                [
                    _fmt_optional_greek(c.get("delta")),
                    _fmt_optional_greek(c.get("gamma")),
                    _fmt_optional_greek(c.get("theta")),
                    _fmt_optional_greek(c.get("vega")),
                    _fmt_optional_greek(c.get("rho")),
                ]
            )
        table.add_row(*row_cells)

    console.print(table)
    if limit and len(contracts) > limit:
        console.print(
            f"[dim](showing {limit} of {len(contracts)} contracts; use --limit 0 to show all)[/dim]"
        )


def _format_fundamentals_value(value: Any) -> str:
    """Format a value for fundamentals display."""
    if value is None:
        return "N/A"
    if isinstance(value, (int, float)):
        return str(value)
    return str(value)


def _income_trend_table(income_statements: list[dict[str, Any]], period_type: str) -> Table | None:
    """Build a compact income trend table (revenue, net income, EPS) for the last 5 periods."""
    if not income_statements:
        return None
    # Use up to 5 periods, skip rows with no revenue
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


@market_app.command("fundamentals")
@async_command
async def get_market_fundamentals(
    symbol: str = typer.Argument(..., help="Equity symbol"),
    periods: int = typer.Option(
        5,
        "--periods",
        "-n",
        help="Number of periods (e.g. 5 years or 5 quarters)",
    ),
    period_type: str = typer.Option(
        "annual",
        "--period-type",
        help="Period type: annual or quarterly",
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Bypass cache and fetch fresh data",
    ),
) -> None:
    """Fetch fundamental data for an equity (financials, ratios, metrics).

    Uses the same cache as in question-driven analysis. Data includes income statement,
    balance sheet, cash flow, and key ratios.
    """
    symbol_upper = symbol.upper()
    cache_manager = container.cache_manager()
    fundamentals_data: dict[str, Any] | None = None

    if not no_cache:
        try:
            entry = await cache_manager.get(
                "get_market_fundamentals",
                symbol=symbol_upper,
                periods=periods,
                period_type=period_type,
            )
            if entry and entry.data:
                fundamentals_data = dict(entry.data)
        except Exception:
            pass

    if fundamentals_data is None:
        try:
            use_case = container.get_stock_fundamentals_use_case()
            response = await use_case.execute(
                GetStockFundamentalsRequest(
                    symbol=symbol_upper,
                    periods=periods,
                    period_type=period_type,
                )
            )
            fundamentals_data = response.fundamentals.model_dump(mode="json")
        except Exception as e:
            handle_cli_error(e, context={"symbol": symbol, "feature": "fundamentals"})
            return

        if not no_cache:
            with contextlib.suppress(Exception):
                await cache_manager.set(
                    "get_market_fundamentals",
                    data=fundamentals_data,
                    metadata={
                        "symbol": symbol_upper,
                        "periods": periods,
                        "period_type": period_type,
                    },
                    symbol=symbol_upper,
                    periods=periods,
                    period_type=period_type,
                )

    # Title and data-availability note
    console.print(f"[bold]Fundamentals for {fundamentals_data.get('symbol', symbol_upper)}[/bold]")
    num_income = len(fundamentals_data.get("income_statements") or [])
    num_balance = len(fundamentals_data.get("balance_sheets") or [])
    num_cashflow = len(fundamentals_data.get("cash_flow_statements") or [])
    ratios = fundamentals_data.get("ratios") or {}
    num_ratios = (
        len([k for k in ratios if k != "metadata" and ratios.get(k) is not None])
        if isinstance(ratios, dict)
        else 0
    )
    console.print(
        f"[dim]Full dataset: {num_income} income, {num_balance} balance sheet, {num_cashflow} cash flow periods, "
        f'plus {num_ratios} ratios (cached). Use [italic]copinance analyze equity {symbol_upper} --question "..."[/italic] '
        "to ask questions about this data.[/dim]\n"
    )

    # Overview table (market cap / EV in B/T)
    overview = Table(title="Overview")
    overview.add_column("Field", style="cyan")
    overview.add_column("Value", style="green")
    overview.add_row(
        "Company",
        _format_fundamentals_value(fundamentals_data.get("company_name")),
    )
    overview.add_row(
        "Sector",
        _format_fundamentals_value(fundamentals_data.get("sector")),
    )
    overview.add_row(
        "Industry",
        _format_fundamentals_value(fundamentals_data.get("industry")),
    )
    overview.add_row(
        "Market cap",
        format_compact_number(fundamentals_data.get("market_cap")),
    )
    overview.add_row(
        "Enterprise value",
        format_compact_number(fundamentals_data.get("enterprise_value")),
    )
    overview.add_row(
        "Current price",
        _format_fundamentals_value(fundamentals_data.get("current_price")),
    )
    overview.add_row(
        "Currency",
        _format_fundamentals_value(fundamentals_data.get("currency")),
    )
    overview.add_row(
        "Fiscal year end",
        _format_fundamentals_value(fundamentals_data.get("fiscal_year_end")),
    )
    overview.add_row(
        "Provider",
        _format_fundamentals_value(fundamentals_data.get("provider")),
    )
    overview.add_row(
        "Data as of",
        _format_fundamentals_value(fundamentals_data.get("data_as_of")),
    )
    console.print(overview)

    # Income trend (revenue, net income, EPS over periods)
    trend = _income_trend_table(
        fundamentals_data.get("income_statements") or [],
        period_type,
    )
    if trend:
        console.print(trend)

    # Growth metrics from full ratio set when present
    if ratios and isinstance(ratios, dict):
        growth_keys = ("revenue_growth", "earnings_growth", "free_cash_flow_growth")
        growth_parts = []
        for k in growth_keys:
            v = ratios.get(k)
            if v is not None:
                try:
                    pct = float(v)
                    growth_parts.append(f"{k.replace('_', ' ').title()}: {pct:+.1f}%")
                except (TypeError, ValueError):
                    pass
        if growth_parts:
            console.print("[bold]Growth (YoY)[/bold]  [dim]from full dataset[/dim]")
            console.print("  " + "  |  ".join(growth_parts))

    # Key ratios if present
    if ratios and isinstance(ratios, dict):
        ratio_keys = [
            "price_to_earnings",
            "price_to_book",
            "return_on_equity",
            "debt_to_equity",
            "current_ratio",
            "operating_margin",
            "net_margin",
        ]

        def _ratio_display(v: Any) -> str:
            if v is None:
                return "N/A"
            try:
                f = float(v)
                return f"{f:.2f}" if abs(f) < 1e6 else f"{f:.1f}"
            except (TypeError, ValueError):
                return str(v)

        ratio_rows = [
            (key.replace("_", " ").title(), _ratio_display(ratios.get(key)))
            for key in ratio_keys
            if ratios.get(key) is not None
        ]
        if ratio_rows:
            ratios_table = Table(title="Key ratios (most recent period)")
            ratios_table.add_column("Ratio", style="cyan")
            ratios_table.add_column("Value", justify="right", style="magenta")
            for label, val in ratio_rows:
                ratios_table.add_row(label, val)
            console.print(ratios_table)
