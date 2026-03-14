"""Market data CLI commands."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from copinanceos.application.use_cases.market import (
    InstrumentSearchMode,
    SearchInstrumentsRequest,
)
from copinanceos.cli.error_handler import handle_cli_error
from copinanceos.cli.utils import async_command
from copinanceos.domain.models.market import MarketDataPoint, OptionsChain, OptionSide
from copinanceos.infrastructure.containers import container

market_app = typer.Typer(help="Market data commands")
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
        console.print("No instruments found", style="yellow")
        return

    table = Table(title=f"Search Results for '{query}'")
    table.add_column("Symbol", style="cyan")
    table.add_column("Name", style="magenta")
    table.add_column("Exchange", style="green")

    for instrument in response.instruments:
        table.add_row(instrument.symbol, instrument.name, instrument.exchange)

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
    """Fetch the latest market quote for an instrument.

    Uses the same cache as agent tools; repeated requests for the same
    symbol are served from cache until expiry or cache clear.
    """
    symbol_upper = symbol.upper()
    cache_manager = container.cache_manager()
    provider = container.market_data_provider()
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
            quote = await provider.get_quote(symbol_upper)
        except Exception as e:
            handle_cli_error(e, context={"symbol": symbol, "feature": "quote"})
            return

        if not no_cache:
            try:
                await cache_manager.set(
                    "get_market_quote",
                    data=quote,
                    metadata={"symbol": symbol_upper},
                    symbol=symbol_upper,
                )
            except Exception:
                pass

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

    Uses the same cache as agent tools; repeated requests for the same
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
    provider = container.market_data_provider()

    rows: list[dict[str, Any]] = []

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
        except Exception:
            pass

    if not rows:
        try:
            history = await provider.get_historical_data(
                symbol=symbol_upper,
                start_date=parsed_start_date,
                end_date=parsed_end_date,
                interval=interval,
            )
        except Exception as e:
            handle_cli_error(e, context={"symbol": symbol, "feature": "history"})
            return

        if not history:
            console.print("No historical market data found", style="yellow")
            return

        rows = _history_rows_from_provider(history)
        try:
            await cache_manager.set(
                "get_historical_market_data",
                data=rows,
                metadata={"symbol": symbol_upper, "interval": interval},
                symbol=symbol_upper,
                start_date=start_str,
                end_date=end_str,
                interval=interval,
            )
        except Exception:
            pass

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
            row.get("open_price", ""),
            row.get("close_price", ""),
            row.get("high_price", ""),
            row.get("low_price", ""),
            str(row.get("volume", "")),
        )

    console.print(table)
    if limit and len(rows) > limit:
        console.print(
            f"[dim](showing {limit} of {len(rows)} rows; use --limit 0 to show all)[/dim]"
        )


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
            c, p = options_chain.calls, options_chain.puts
            raw = [x for pair in zip(c, p, strict=False) for x in pair] + c[len(p) :] + p[len(c) :]
        contracts = [
            {
                "contract_symbol": c.contract_symbol,
                "side": c.side.value,
                "strike": c.strike,
                "last_price": c.last_price,
                "implied_volatility": c.implied_volatility,
                "open_interest": c.open_interest,
                "volume": c.volume,
            }
            for c in raw
        ]
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
    contracts = [
        {
            "contract_symbol": c.get("contract_symbol", ""),
            "side": c.get("side", ""),
            "strike": c.get("strike"),
            "last_price": c.get("last_price"),
            "implied_volatility": c.get("implied_volatility"),
            "open_interest": c.get("open_interest"),
            "volume": c.get("volume"),
        }
        for c in raw_contracts
    ]
    return underlying_price, exp_str, contracts


@market_app.command("options")
@async_command
async def get_options_chain(
    underlying_symbol: str = typer.Argument(..., help="Underlying symbol"),
    expiration_date: str | None = typer.Option(
        None,
        "--expiration",
        help="Optional expiration date in YYYY-MM-DD format",
    ),
    option_side: OptionSide = typer.Option(
        OptionSide.ALL,
        "--side",
        help="Options side to display",
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
        help="Bypass cache and fetch fresh data",
    ),
) -> None:
    """Fetch an options chain snapshot for an underlying symbol.

    Uses the same cache as agent tools; repeated requests for the same
    underlying/expiration are served from cache until expiry or cache clear.
    """
    symbol_upper = underlying_symbol.upper()
    cache_manager = container.cache_manager()
    provider = container.market_data_provider()
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
            chain = await provider.get_options_chain(
                underlying_symbol=symbol_upper,
                expiration_date=expiration_date,
            )
        except Exception as e:
            handle_cli_error(
                e, context={"underlying_symbol": underlying_symbol, "feature": "options"}
            )
            return

        options_data = chain
        if not no_cache:
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

    table = Table(title=f"{option_side.value.capitalize()} contracts")
    table.add_column("Contract", style="cyan")
    table.add_column("Side", style="magenta")
    table.add_column("Strike", justify="right")
    table.add_column("Last", justify="right")
    table.add_column("IV", justify="right")
    table.add_column("OI", justify="right")
    table.add_column("Vol", justify="right")

    to_show = contracts[:limit] if limit else contracts
    for c in to_show:
        table.add_row(
            c["contract_symbol"],
            c["side"],
            str(c["strike"]),
            str(c["last_price"]) if c.get("last_price") is not None else "-",
            str(c["implied_volatility"]) if c.get("implied_volatility") is not None else "-",
            str(c["open_interest"]) if c.get("open_interest") is not None else "-",
            str(c["volume"]) if c.get("volume") is not None else "-",
        )

    console.print(table)
    if limit and len(contracts) > limit:
        console.print(
            f"[dim](showing {limit} of {len(contracts)} contracts; use --limit 0 to show all)[/dim]"
        )
