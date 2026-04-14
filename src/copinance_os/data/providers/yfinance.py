"""yfinance data provider implementation.

yfinance is a free, open-source library for downloading market data from Yahoo Finance.
This implementation provides market data and basic fundamental data.

Example usage:
    ```python
    from copinance_os.data.providers import YFinanceMarketProvider

    provider = YFinanceMarketProvider()
    quote = await provider.get_quote("AAPL")
    historical = await provider.get_historical_data("AAPL", start_date, end_date)
    ```

To use a custom provider, simply implement the MarketDataProvider interface:
    ```python
    from copinance_os.domain.ports.data_providers import MarketDataProvider

    class MyCustomProvider(MarketDataProvider):
        async def get_quote(self, symbol: str) -> dict[str, Any]:
            # Your implementation
            pass
    ```
"""

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, cast

import structlog
from typing_extensions import override

try:
    import pandas as pd  # type: ignore[import-untyped]
    import yfinance as yf  # type: ignore[import-untyped]
    from pandas import DataFrame

    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    yf = None
    DataFrame = None  # type: ignore[misc, assignment]
    pd = None  # type: ignore[assignment]

from copinance_os.domain.exceptions import DataProviderError, ValidationError
from copinance_os.domain.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    FinancialRatios,
    FinancialStatementPeriod,
    IncomeStatement,
    StockFundamentals,
)
from copinance_os.domain.models.market import (
    MarketDataPoint,
    OptionContract,
    OptionsChain,
    OptionSide,
)
from copinance_os.domain.ports.data_providers import (
    FundamentalDataProvider,
    MarketDataProvider,
)

logger = structlog.get_logger(__name__)


def _safe_decimal(value: Any) -> Decimal | None:
    """Safely convert provider values to Decimal."""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            if isinstance(value, float) and (value != value):
                return None
            return Decimal(str(value))
        if isinstance(value, str):
            if value.lower() in ("nan", "none", "null", ""):
                return None
            return Decimal(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return None


def _select_options_expiration_string(
    available_expirations: list[str],
    explicit_expiration: str | None,
    *,
    as_of: date | None = None,
) -> str:
    """Choose option expiry string YYYY-MM-DD.

    When ``explicit_expiration`` is omitted, returns the earliest listed expiry whose
    calendar date is **on or after** ``as_of`` (default: local **today**), so default
    chains are not an already-expired front month after the session rolls. If every
    listing is before ``as_of``, returns the latest listed date (chain may be expired;
    BSM Greeks may be unavailable).
    """
    if explicit_expiration is not None:
        return explicit_expiration
    if not available_expirations:
        raise ValidationError("available_expirations", "must not be empty")
    parsed = sorted({datetime.strptime(x, "%Y-%m-%d").date() for x in available_expirations})
    today = as_of if as_of is not None else date.today()
    for d in parsed:
        if d >= today:
            return d.strftime("%Y-%m-%d")
    return parsed[-1].strftime("%Y-%m-%d")


def _yahoo_option_implied_volatility_to_sigma(iv: Decimal | None) -> Decimal | None:
    """Convert Yahoo option-chain implied vol to annualized σ for BSM / QuantLib.

    yfinance usually returns σ as a fraction (e.g. ``0.25`` ≈ 25% vol). Some rows ship
    the same figure in percent points (e.g. ``13.67`` ≈ 13.67% vol). Values strictly
    greater than ``1`` are treated as percent points and divided by 100.

    Genuinely extreme fractional σ above 100% (e.g. ``1.2``) would be mis-scaled; that
    is uncommon for liquid chains. See developer guide (options chain metadata).
    """
    if iv is None or iv <= 0:
        return iv
    if iv > Decimal("1"):
        return iv / Decimal("100")
    return iv


def _safe_int(value: Any) -> int | None:
    """Safely convert provider values to int."""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            if isinstance(value, float) and (value != value):
                return None
            return int(value)
        if isinstance(value, str):
            if value.lower() in ("nan", "none", "null", ""):
                return None
            return int(float(value))
    except (ValueError, TypeError, OverflowError):
        return None
    return None


class YFinanceMarketProvider(MarketDataProvider):
    """yfinance implementation of MarketDataProvider.

    Provides free market data from Yahoo Finance including:
    - Real-time quotes
    - Historical price data (OHLCV)
    - Intraday data

    This is a synchronous library wrapped in async methods for compatibility.
    """

    def __init__(self) -> None:
        """Initialize yfinance market data provider."""
        self._provider_name = "yfinance"
        logger.info("Initialized yfinance market data provider")

    @override
    async def is_available(self) -> bool:
        """Check if yfinance is available."""
        if not YFINANCE_AVAILABLE:
            return False
        try:
            # Quick test to see if we can fetch data
            test_ticker = await asyncio.to_thread(lambda: yf.Ticker("AAPL").info)
            return test_ticker is not None
        except Exception as e:
            logger.warning("yfinance availability check failed", error=str(e))
            return False

    @override
    def get_provider_name(self) -> str:
        """Get provider name."""
        return self._provider_name

    @override
    async def get_quote(self, symbol: str) -> dict[str, Any]:
        """Get current quote for a symbol.

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL")

        Returns:
            Dictionary with quote data including:
            - current_price: Current trading price
            - previous_close: Previous day's closing price
            - open: Today's opening price
            - high: Today's high price
            - low: Today's low price
            - volume: Trading volume
            - market_cap: Market capitalization
            - currency: Currency code
            - exchange: Exchange name
        """
        try:
            ticker = await asyncio.to_thread(lambda: yf.Ticker(symbol))
            info = await asyncio.to_thread(lambda: ticker.info)

            # Get latest price data
            hist = await asyncio.to_thread(lambda: ticker.history(period="1d", interval="1m"))

            quote = {
                "symbol": symbol.upper(),
                "longName": info.get("longName"),
                "shortName": info.get("shortName"),
                "current_price": Decimal(
                    str(info.get("currentPrice", info.get("regularMarketPrice", 0)))
                ),
                "previous_close": Decimal(str(info.get("previousClose", 0))),
                "open": Decimal(str(info.get("open", 0))),
                "high": Decimal(str(info.get("dayHigh", info.get("regularMarketDayHigh", 0)))),
                "low": Decimal(str(info.get("dayLow", info.get("regularMarketDayLow", 0)))),
                "volume": int(info.get("volume", info.get("regularMarketVolume", 0))),
                "market_cap": int(info.get("marketCap", 0)) if info.get("marketCap") else None,
                "currency": info.get("currency", "USD"),
                "exchange": info.get("exchange", ""),
                "timestamp": datetime.now(UTC).isoformat(),
            }

            # Add latest price from history if available
            if not hist.empty:
                latest = hist.iloc[-1]
                quote["current_price"] = Decimal(str(float(latest["Close"])))
                quote["volume"] = int(latest["Volume"])

            logger.info("Fetched quote", symbol=symbol, provider=self._provider_name)
            return quote

        except Exception as e:
            logger.error("Failed to fetch quote", symbol=symbol, error=str(e))
            raise DataProviderError(
                self._provider_name, "get_quote", f"Failed to fetch quote for {symbol}: {e}"
            ) from e

    @override
    async def get_historical_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
    ) -> list[MarketDataPoint]:
        """Get historical market data.

        Args:
            symbol: Stock ticker symbol
            start_date: Start date for historical data
            end_date: End date for historical data
            interval: Data interval (1d, 1wk, 1mo, etc.)

        Returns:
            List of MarketDataPoint objects with OHLCV data
        """
        try:
            if not YFINANCE_AVAILABLE:
                raise ImportError(
                    "yfinance is not installed. Install it with: pip install yfinance"
                )
            ticker = await asyncio.to_thread(lambda: yf.Ticker(symbol))

            # yfinance uses period or start/end dates
            hist: DataFrame = await asyncio.to_thread(
                lambda: ticker.history(start=start_date, end=end_date, interval=interval),
            )

            if hist.empty:
                logger.warning(
                    "No historical data found", symbol=symbol, start=start_date, end=end_date
                )
                return []

            stock_data_list: list[MarketDataPoint] = []
            for timestamp, row in hist.iterrows():
                ts = (
                    timestamp.to_pydatetime()
                    if hasattr(timestamp, "to_pydatetime")
                    else datetime.fromisoformat(str(timestamp))
                )
                stock_data = MarketDataPoint(
                    symbol=symbol.upper(),
                    timestamp=cast(datetime, ts),
                    open_price=Decimal(str(float(row["Open"]))),
                    close_price=Decimal(str(float(row["Close"]))),
                    high_price=Decimal(str(float(row["High"]))),
                    low_price=Decimal(str(float(row["Low"]))),
                    volume=int(row["Volume"]),
                    metadata={
                        "interval": interval,
                        "provider": self._provider_name,
                    },
                )
                stock_data_list.append(stock_data)

            logger.info(
                "Fetched historical data",
                symbol=symbol,
                count=len(stock_data_list),
                provider=self._provider_name,
            )
            return stock_data_list

        except Exception as e:
            logger.error("Failed to fetch historical data", symbol=symbol, error=str(e))
            raise DataProviderError(
                self._provider_name,
                "get_historical_data",
                f"Failed to fetch historical data for {symbol}: {e}",
            ) from e

    @override
    async def get_intraday_data(
        self,
        symbol: str,
        interval: str = "1min",
    ) -> list[MarketDataPoint]:
        """Get intraday market data.

        Args:
            symbol: Stock ticker symbol
            interval: Data interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h)

        Returns:
            List of MarketDataPoint objects with intraday OHLCV data
        """
        try:
            if not YFINANCE_AVAILABLE:
                raise ImportError(
                    "yfinance is not installed. Install it with: pip install yfinance"
                )
            # For intraday, we get the last trading day's data
            end_date = datetime.now(UTC)
            start_date = end_date - timedelta(days=7)  # Get last week for intraday

            ticker = await asyncio.to_thread(lambda: yf.Ticker(symbol))

            hist: DataFrame = await asyncio.to_thread(
                lambda: ticker.history(start=start_date, end=end_date, interval=interval),
            )

            if hist.empty:
                logger.warning("No intraday data found", symbol=symbol, interval=interval)
                return []

            stock_data_list: list[MarketDataPoint] = []
            for timestamp, row in hist.iterrows():
                ts = (
                    timestamp.to_pydatetime()
                    if hasattr(timestamp, "to_pydatetime")
                    else datetime.fromisoformat(str(timestamp))
                )
                stock_data = MarketDataPoint(
                    symbol=symbol.upper(),
                    timestamp=cast(datetime, ts),
                    open_price=Decimal(str(float(row["Open"]))),
                    close_price=Decimal(str(float(row["Close"]))),
                    high_price=Decimal(str(float(row["High"]))),
                    low_price=Decimal(str(float(row["Low"]))),
                    volume=int(row["Volume"]),
                    metadata={
                        "interval": interval,
                        "provider": self._provider_name,
                        "data_type": "intraday",
                    },
                )
                stock_data_list.append(stock_data)

            logger.info(
                "Fetched intraday data",
                symbol=symbol,
                count=len(stock_data_list),
                interval=interval,
                provider=self._provider_name,
            )
            return stock_data_list

        except Exception as e:
            logger.error("Failed to fetch intraday data", symbol=symbol, error=str(e))
            raise DataProviderError(
                self._provider_name,
                "get_intraday_data",
                f"Failed to fetch intraday data for {symbol}: {e}",
            ) from e

    @override
    async def search_instruments(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search for market instruments by symbol or name using yfinance Search.

        Args:
            query: Search query (can be symbol or company name)
            limit: Maximum number of results to return

        Returns:
            List of matching market instruments with symbol, name, exchange, etc.
        """
        try:
            if not YFINANCE_AVAILABLE:
                raise ImportError(
                    "yfinance is not installed. Install it with: pip install yfinance"
                )

            # Use yfinance Search to find stocks by name or symbol
            search = await asyncio.to_thread(lambda: yf.Search(query, max_results=limit))

            # Get quotes from search results
            quotes = search.quotes
            if not quotes:
                logger.debug("No search results found", query=query)
                return []

            # Format results (yfinance Search returns dicts with lowercase keys:
            # symbol, longname, shortname, exchange, exchDisp, quoteType, etc.)
            results: list[dict[str, Any]] = []
            for quote in quotes[:limit]:
                result = {
                    "symbol": quote.get("symbol", "").upper(),
                    "name": quote.get("longname") or quote.get("shortname", ""),
                    "exchange": quote.get("exchange", ""),
                    "exch_disp": quote.get("exchDisp", ""),
                    "quoteType": quote.get("quoteType", ""),
                }
                # Only include stock/equity results, filter out other types
                if result["quoteType"] in ["EQUITY", "ETF", ""]:
                    results.append(result)

            logger.info(
                "Searched market instruments",
                query=query,
                results_count=len(results),
                provider=self._provider_name,
            )
            return results

        except Exception as e:
            logger.warning("Failed to search market instruments", query=query, error=str(e))
            return []

    @override
    async def get_options_chain(
        self,
        underlying_symbol: str,
        expiration_date: str | None = None,
    ) -> OptionsChain:
        """Get the options chain for an underlying instrument."""
        try:
            if not YFINANCE_AVAILABLE:
                raise ImportError(
                    "yfinance is not installed. Install it with: pip install yfinance"
                )

            ticker = await asyncio.to_thread(lambda: yf.Ticker(underlying_symbol))
            available_expirations = await asyncio.to_thread(lambda: list(ticker.options))

            if not available_expirations:
                raise DataProviderError(
                    self._provider_name,
                    "get_options_chain",
                    f"No listed options available for {underlying_symbol}",
                )

            selected_expiration = _select_options_expiration_string(
                available_expirations,
                expiration_date,
            )
            if selected_expiration not in available_expirations:
                raise ValidationError(
                    "expiration_date",
                    f"Expiration {selected_expiration} is not available for {underlying_symbol}",
                )

            option_chain = await asyncio.to_thread(
                lambda: ticker.option_chain(selected_expiration),
            )
            info = await asyncio.to_thread(lambda: ticker.info)

            def _to_contracts(frame: DataFrame, side: OptionSide) -> list[OptionContract]:
                contracts: list[OptionContract] = []
                for _, row in frame.iterrows():
                    expiration = datetime.strptime(selected_expiration, "%Y-%m-%d").date()
                    contract = OptionContract(
                        underlying_symbol=underlying_symbol.upper(),
                        contract_symbol=str(row.get("contractSymbol", "")),
                        side=side,
                        strike=_safe_decimal(row.get("strike")) or Decimal("0"),
                        expiration_date=expiration,
                        last_price=_safe_decimal(row.get("lastPrice")),
                        bid=_safe_decimal(row.get("bid")),
                        ask=_safe_decimal(row.get("ask")),
                        volume=_safe_int(row.get("volume")),
                        open_interest=_safe_int(row.get("openInterest")),
                        greeks=None,
                        implied_volatility=_yahoo_option_implied_volatility_to_sigma(
                            _safe_decimal(row.get("impliedVolatility"))
                        ),
                        in_the_money=(
                            bool(row.get("inTheMoney"))
                            if row.get("inTheMoney") is not None
                            else None
                        ),
                        currency=info.get("currency", "USD"),
                        metadata={
                            "provider": self._provider_name,
                            "last_trade_date": str(row.get("lastTradeDate", "")),
                        },
                    )
                    contracts.append(contract)
                return contracts

            underlying_price = _safe_decimal(
                info.get("currentPrice") or info.get("regularMarketPrice")
            )
            if underlying_price is None:
                fast_info = await asyncio.to_thread(lambda: getattr(ticker, "fast_info", {}))
                if isinstance(fast_info, dict):
                    underlying_price = _safe_decimal(
                        fast_info.get("lastPrice") or fast_info.get("regularMarketPrice")
                    )

            result = OptionsChain(
                underlying_symbol=underlying_symbol.upper(),
                expiration_date=datetime.strptime(selected_expiration, "%Y-%m-%d").date(),
                available_expirations=[
                    datetime.strptime(expiration, "%Y-%m-%d").date()
                    for expiration in available_expirations
                ],
                underlying_price=underlying_price,
                calls=_to_contracts(option_chain.calls, OptionSide.CALL),
                puts=_to_contracts(option_chain.puts, OptionSide.PUT),
                currency=info.get("currency", "USD"),
                metadata={"provider": self._provider_name},
            )
            logger.info(
                "Fetched options chain",
                underlying_symbol=underlying_symbol,
                expiration_date=selected_expiration,
                calls=len(result.calls),
                puts=len(result.puts),
                provider=self._provider_name,
            )
            return result
        except Exception as e:
            logger.error(
                "Failed to fetch options chain",
                underlying_symbol=underlying_symbol,
                error=str(e),
            )
            raise DataProviderError(
                self._provider_name,
                "get_options_chain",
                f"Failed to fetch options chain for {underlying_symbol}: {e}",
            ) from e


class YFinanceFundamentalProvider(FundamentalDataProvider):
    """yfinance implementation of FundamentalDataProvider.

    Provides basic fundamental data from Yahoo Finance including:
    - Financial statements (income statement, balance sheet, cash flow)
    - Company information
    - Key financial metrics

    Note: yfinance has limited fundamental data compared to specialized providers.
    For comprehensive fundamentals or SEC filings, plug in a dedicated fundamental data provider.
    """

    def __init__(self, cache_ttl_seconds: int = 3600) -> None:
        """Initialize yfinance fundamental data provider.

        Args:
            cache_ttl_seconds: Time-to-live for cached data in seconds (default: 1 hour)
        """
        self._provider_name = "yfinance"
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cache: dict[str, tuple[StockFundamentals, datetime]] = {}
        logger.info(
            "Initialized yfinance fundamental data provider",
            cache_ttl_seconds=cache_ttl_seconds,
        )

    @override
    async def is_available(self) -> bool:
        """Check if yfinance is available."""
        if not YFINANCE_AVAILABLE:
            return False
        try:
            test_ticker = await asyncio.to_thread(lambda: yf.Ticker("AAPL").info)
            return test_ticker is not None
        except Exception as e:
            logger.warning("yfinance availability check failed", error=str(e))
            return False

    @override
    def get_provider_name(self) -> str:
        """Get provider name."""
        return self._provider_name

    @override
    async def get_financial_statements(
        self,
        symbol: str,
        statement_type: str,
        period: str = "annual",
    ) -> dict[str, Any]:
        """Get financial statements.

        Args:
            symbol: Stock ticker symbol
            statement_type: income_statement, balance_sheet, or cash_flow
            period: annual or quarterly

        Returns:
            Dictionary with financial statement data
        """
        try:
            if not YFINANCE_AVAILABLE:
                raise ImportError(
                    "yfinance is not installed. Install it with: pip install yfinance"
                )
            ticker = await asyncio.to_thread(lambda: yf.Ticker(symbol))

            # Map statement types to yfinance properties
            # Note: yfinance uses properties, not methods, so we access them directly
            statement_map = {
                "income_statement": "financials" if period == "annual" else "quarterly_financials",
                "balance_sheet": (
                    "balance_sheet" if period == "annual" else "quarterly_balance_sheet"
                ),
                "cash_flow": "cashflow" if period == "annual" else "quarterly_cashflow",
            }

            if statement_type not in statement_map:
                raise ValidationError("statement_type", f"Invalid statement_type: {statement_type}")

            property_name = statement_map[statement_type]

            # yfinance properties are accessed directly, not called
            def _get_statement() -> DataFrame:
                prop = getattr(ticker, property_name)
                # If it's a property, access it; if it's a method, call it
                if callable(prop):
                    return cast(DataFrame, prop())
                return cast(DataFrame, prop)

            statement_df: DataFrame = await asyncio.to_thread(_get_statement)

            if statement_df.empty:
                logger.warning(
                    "No financial statement data found",
                    symbol=symbol,
                    statement_type=statement_type,
                    period=period,
                )
                return {"symbol": symbol, "statement_type": statement_type, "data": {}}

            # Convert DataFrame to dictionary
            statement_data = statement_df.to_dict(orient="index")

            result = {
                "symbol": symbol.upper(),
                "statement_type": statement_type,
                "period": period,
                "data": {
                    str(k): {str(col): float(v) for col, v in row.items()}
                    for k, row in statement_data.items()
                },
                "provider": self._provider_name,
            }

            logger.info(
                "Fetched financial statement",
                symbol=symbol,
                statement_type=statement_type,
                period=period,
                provider=self._provider_name,
            )
            return result

        except Exception as e:
            logger.error(
                "Failed to fetch financial statement",
                symbol=symbol,
                statement_type=statement_type,
                error=str(e),
            )
            raise DataProviderError(
                self._provider_name,
                "get_financial_statements",
                f"Failed to fetch {statement_type} for {symbol}: {e}",
            ) from e

    @override
    async def get_sec_filings(
        self,
        symbol: str,
        filing_types: list[str],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get SEC filings (stub: yfinance does not expose full SEC filing feeds).

        Note: yfinance has limited SEC filing support. Use a dedicated SEC/fundamental
        provider for comprehensive filing metadata and content.

        This method returns an empty list until such a provider is wired in.
        """
        logger.warning(
            "yfinance has limited SEC filing support",
            symbol=symbol,
            suggestion="Use a dedicated SEC/fundamental data provider for filings",
        )
        # yfinance doesn't provide comprehensive SEC filing access
        # Return empty list - developers should use a dedicated SEC provider
        return []

    @override
    async def get_earnings_transcripts(
        self,
        symbol: str,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        """Get earnings call transcripts.

        Note: yfinance doesn't provide earnings transcripts. For transcripts,
        consider implementing a dedicated provider or using services like
        Seeking Alpha, Fidelity, or other transcript providers.
        """
        logger.warning(
            "yfinance doesn't provide earnings transcripts",
            symbol=symbol,
            suggestion="Consider implementing a dedicated transcript provider",
        )
        return []

    @override
    async def get_esg_metrics(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """Get ESG metrics.

        Note: yfinance has limited ESG data. For comprehensive ESG metrics,
        consider integrating with Sustainalytics, MSCI, or other ESG providers.
        """
        try:
            ticker = await asyncio.to_thread(lambda: yf.Ticker(symbol))
            info = await asyncio.to_thread(lambda: ticker.info)

            # Extract any ESG-related fields from info
            esg_data = {
                "symbol": symbol.upper(),
                "provider": self._provider_name,
                "note": "yfinance has limited ESG data",
            }

            # Check for ESG-related fields (yfinance may have some)
            if "esgScores" in info:
                esg_data["scores"] = info["esgScores"]

            logger.info("Fetched ESG metrics", symbol=symbol, provider=self._provider_name)
            return esg_data

        except Exception as e:
            logger.warning("Failed to fetch ESG metrics", symbol=symbol, error=str(e))
            return {
                "symbol": symbol.upper(),
                "provider": self._provider_name,
                "error": "ESG data not available via yfinance",
            }

    @override
    async def get_insider_trading(
        self,
        symbol: str,
        lookback_days: int = 90,
    ) -> list[dict[str, Any]]:
        """Get insider trading activity.

        Note: yfinance doesn't provide insider trading data. For insider trading
        information, consider implementing a provider that accesses SEC Form 4 filings.
        """
        logger.warning(
            "yfinance doesn't provide insider trading data",
            symbol=symbol,
            suggestion="Consider implementing a SEC Form 4 provider",
        )
        return []

    def _safe_decimal(self, value: Any) -> Decimal | None:
        """Safely convert value to Decimal, handling None, NaN, and invalid values."""
        if value is None:
            return None
        try:
            if isinstance(value, (int, float)):
                # Check for NaN
                if isinstance(value, float) and (value != value):  # NaN check
                    return None
                return Decimal(str(value))
            if isinstance(value, str):
                if value.lower() in ("nan", "none", "null", ""):
                    return None
                return Decimal(value)
            return None
        except (ValueError, TypeError, OverflowError):
            return None

    def _safe_int(self, value: Any) -> int | None:
        """Safely convert value to int, handling None and invalid values."""
        if value is None:
            return None
        try:
            if isinstance(value, (int, float)):
                if isinstance(value, float) and (value != value):  # NaN check
                    return None
                return int(value)
            if isinstance(value, str):
                if value.lower() in ("nan", "none", "null", ""):
                    return None
                return int(float(value))
            return None
        except (ValueError, TypeError, OverflowError):
            return None

    def _parse_financial_statement_period(
        self, period_str: str, period_type: str
    ) -> FinancialStatementPeriod | None:
        """Parse period string from yfinance into FinancialStatementPeriod."""
        try:
            # yfinance typically uses datetime or date strings
            if isinstance(period_str, datetime):
                period_date = period_str
            elif isinstance(period_str, str):
                # Try parsing various date formats
                for fmt in ["%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
                    try:
                        period_date = datetime.strptime(period_str.split()[0], fmt)
                        break
                    except ValueError:
                        continue
                else:
                    return None
            else:
                return None

            fiscal_year = period_date.year
            fiscal_quarter = None
            if period_type == "quarterly":
                # Estimate quarter from month (approximate)
                month = period_date.month
                fiscal_quarter = ((month - 1) // 3) + 1

            return FinancialStatementPeriod(
                period_end_date=period_date,
                period_type=period_type,
                fiscal_year=fiscal_year,
                fiscal_quarter=fiscal_quarter,
            )
        except Exception:
            return None

    def _calculate_ratios(
        self,
        income: IncomeStatement | None,
        balance: BalanceSheet | None,
        cashflow: CashFlowStatement | None,
        market_cap: Decimal | None,
        current_price: Decimal | None,
        shares_outstanding: int | None,
        enterprise_value: Decimal | None = None,
        income_statements: list[IncomeStatement] | None = None,
        cash_flow_statements: list[CashFlowStatement] | None = None,
    ) -> FinancialRatios:
        """Calculate financial ratios from statements."""
        ratios_dict: dict[str, Decimal | None | dict[str, str]] = {}

        if income and balance:
            # Profitability Ratios
            if income.total_revenue and income.total_revenue > 0:
                if income.gross_profit:
                    ratios_dict["gross_margin"] = (
                        income.gross_profit / income.total_revenue
                    ) * Decimal("100")
                if income.operating_income:
                    ratios_dict["operating_margin"] = (
                        income.operating_income / income.total_revenue
                    ) * Decimal("100")
                if income.net_income:
                    ratios_dict["net_margin"] = (
                        income.net_income / income.total_revenue
                    ) * Decimal("100")

            # Return Ratios
            if balance.total_assets and balance.total_assets > 0 and income.net_income:
                ratios_dict["return_on_assets"] = (
                    income.net_income / balance.total_assets
                ) * Decimal("100")
            if balance.total_equity and balance.total_equity > 0 and income.net_income:
                ratios_dict["return_on_equity"] = (
                    income.net_income / balance.total_equity
                ) * Decimal("100")

            # Return on Invested Capital (ROIC)
            # ROIC = (Operating Income - Taxes) / Invested Capital
            # Invested Capital = Total Assets - Cash - Non-interest bearing current liabilities
            # Simplified: Invested Capital = Total Assets - Cash - (Current Liabilities - Short-term Debt)
            if (
                income.operating_income
                and balance.total_assets
                and balance.cash_and_cash_equivalents is not None
                and balance.current_liabilities is not None
            ):
                # Calculate NOPAT (Net Operating Profit After Tax)
                # Approximate tax rate from income statement
                tax_rate = Decimal("0")
                if (
                    income.income_before_tax
                    and income.income_before_tax > 0
                    and income.income_tax_expense
                ):
                    tax_rate = income.income_tax_expense / income.income_before_tax
                nopat = income.operating_income * (Decimal("1") - tax_rate)

                # Calculate Invested Capital
                # Invested Capital = Total Assets - Cash - (Current Liabilities - Short-term Debt)
                short_term_debt = balance.short_term_debt or Decimal("0")
                non_interest_bearing_liabilities = balance.current_liabilities - short_term_debt
                cash = balance.cash_and_cash_equivalents or Decimal("0")
                invested_capital = balance.total_assets - cash - non_interest_bearing_liabilities

                if invested_capital > 0:
                    ratios_dict["return_on_invested_capital"] = (
                        nopat / invested_capital
                    ) * Decimal("100")

            # Liquidity Ratios
            if balance.current_liabilities and balance.current_liabilities > 0:
                if balance.current_assets:
                    ratios_dict["current_ratio"] = (
                        balance.current_assets / balance.current_liabilities
                    )
                if balance.cash_and_cash_equivalents:
                    quick_assets = (balance.cash_and_cash_equivalents or Decimal("0")) + (
                        balance.accounts_receivable or Decimal("0")
                    )
                    ratios_dict["quick_ratio"] = quick_assets / balance.current_liabilities
                    ratios_dict["cash_ratio"] = (
                        balance.cash_and_cash_equivalents / balance.current_liabilities
                    )

            # Leverage Ratios
            if balance.total_equity and balance.total_equity > 0:
                total_debt = (balance.short_term_debt or Decimal("0")) + (
                    balance.long_term_debt or Decimal("0")
                )
                if total_debt > 0:
                    ratios_dict["debt_to_equity"] = total_debt / balance.total_equity
                if balance.total_assets and balance.total_assets > 0:
                    ratios_dict["debt_to_assets"] = total_debt / balance.total_assets
                    ratios_dict["equity_ratio"] = balance.total_equity / balance.total_assets

            # Interest Coverage
            if income.interest_expense and income.interest_expense > 0 and income.operating_income:
                ratios_dict["interest_coverage"] = income.operating_income / income.interest_expense

            # Efficiency Ratios
            if balance.total_assets and balance.total_assets > 0 and income.total_revenue:
                ratios_dict["asset_turnover"] = income.total_revenue / balance.total_assets
            if balance.inventory and balance.inventory > 0 and income.cost_of_revenue:
                # Approximate inventory turnover (would need average inventory for accuracy)
                ratios_dict["inventory_turnover"] = income.cost_of_revenue / balance.inventory
            if (
                balance.accounts_receivable
                and balance.accounts_receivable > 0
                and income.total_revenue
            ):
                # Approximate receivables turnover
                ratios_dict["receivables_turnover"] = (
                    income.total_revenue / balance.accounts_receivable
                )

        # Valuation Ratios (require market data)
        if income and income.earnings_per_share and income.earnings_per_share > 0 and current_price:
            ratios_dict["price_to_earnings"] = current_price / income.earnings_per_share
        if balance and balance.total_equity and shares_outstanding and shares_outstanding > 0:
            book_value_per_share = balance.total_equity / Decimal(str(shares_outstanding))
            if book_value_per_share > 0 and current_price:
                ratios_dict["price_to_book"] = current_price / book_value_per_share
        if income and income.total_revenue and shares_outstanding and shares_outstanding > 0:
            sales_per_share = income.total_revenue / Decimal(str(shares_outstanding))
            if sales_per_share > 0 and current_price:
                ratios_dict["price_to_sales"] = current_price / sales_per_share
        if cashflow and cashflow.free_cash_flow and shares_outstanding and shares_outstanding > 0:
            fcf_per_share = cashflow.free_cash_flow / Decimal(str(shares_outstanding))
            if fcf_per_share > 0 and current_price:
                ratios_dict["price_to_free_cash_flow"] = current_price / fcf_per_share

        # EV/EBITDA Ratio
        # EBITDA = Operating Income + Depreciation + Amortization
        if enterprise_value and enterprise_value > 0 and income and income.operating_income:
            # Get depreciation and amortization from cash flow statement
            depreciation = (
                cashflow.depreciation_amortization
                if cashflow and cashflow.depreciation_amortization
                else Decimal("0")
            )
            ebitda = income.operating_income + depreciation
            if ebitda > 0:
                ratios_dict["enterprise_value_to_ebitda"] = enterprise_value / ebitda

        # Growth Rates (compare current period with previous period)
        if income_statements and len(income_statements) >= 2:
            current_income = income_statements[0]
            previous_income = income_statements[1]

            # Revenue Growth
            if (
                current_income.total_revenue
                and previous_income.total_revenue
                and previous_income.total_revenue > 0
            ):
                revenue_growth = (
                    (current_income.total_revenue - previous_income.total_revenue)
                    / previous_income.total_revenue
                ) * Decimal("100")
                ratios_dict["revenue_growth"] = revenue_growth

            # Earnings Growth
            if (
                current_income.net_income
                and previous_income.net_income
                and previous_income.net_income != 0
            ):
                earnings_growth = (
                    (current_income.net_income - previous_income.net_income)
                    / abs(previous_income.net_income)
                ) * Decimal("100")
                ratios_dict["earnings_growth"] = earnings_growth

        if cash_flow_statements and len(cash_flow_statements) >= 2:
            current_cashflow = cash_flow_statements[0]
            previous_cashflow = cash_flow_statements[1]

            # Free Cash Flow Growth
            if (
                current_cashflow.free_cash_flow
                and previous_cashflow.free_cash_flow
                and previous_cashflow.free_cash_flow != 0
            ):
                fcf_growth = (
                    (current_cashflow.free_cash_flow - previous_cashflow.free_cash_flow)
                    / abs(previous_cashflow.free_cash_flow)
                ) * Decimal("100")
                ratios_dict["free_cash_flow_growth"] = fcf_growth

        # Add metadata about ratio calculations
        ratios_metadata: dict[str, str] = {
            "provider": "yfinance",
            "calculation_method": "direct",
            "has_growth_rates": (
                "true" if (income_statements and len(income_statements) >= 2) else "false"
            ),
        }

        # Create FinancialRatios from calculated ratios
        # ratios_dict is dict[str, Decimal | None] which matches FinancialRatios field types
        ratios_dict["metadata"] = ratios_metadata
        return FinancialRatios.model_validate(ratios_dict)

    def _get_cache_key(self, symbol: str, periods: int, period_type: str) -> str:
        """Generate cache key for fundamentals request.

        Args:
            symbol: Stock symbol
            periods: Number of periods
            period_type: Period type (annual/quarterly)

        Returns:
            Cache key string
        """
        return f"{symbol.upper()}:{periods}:{period_type}"

    def _get_cached_fundamentals(
        self, symbol: str, periods: int, period_type: str
    ) -> StockFundamentals | None:
        """Get cached fundamentals if available and not expired.

        Args:
            symbol: Stock symbol
            periods: Number of periods
            period_type: Period type (annual/quarterly)

        Returns:
            Cached StockFundamentals if available and valid, None otherwise
        """
        cache_key = self._get_cache_key(symbol, periods, period_type)

        if cache_key not in self._cache:
            return None

        cached_data, cached_at = self._cache[cache_key]
        age_seconds = (datetime.now(UTC) - cached_at).total_seconds()

        if age_seconds > self._cache_ttl_seconds:
            # Cache expired, remove it
            del self._cache[cache_key]
            logger.debug(
                "Cache expired",
                symbol=symbol,
                cache_key=cache_key,
                age_seconds=age_seconds,
            )
            return None

        logger.debug("Cache hit", symbol=symbol, cache_key=cache_key, age_seconds=age_seconds)
        return cached_data

    def _cache_fundamentals(
        self, symbol: str, periods: int, period_type: str, fundamentals: StockFundamentals
    ) -> None:
        """Cache fundamentals data.

        Args:
            symbol: Stock symbol
            periods: Number of periods
            period_type: Period type (annual/quarterly)
            fundamentals: StockFundamentals to cache
        """
        cache_key = self._get_cache_key(symbol, periods, period_type)
        self._cache[cache_key] = (fundamentals, datetime.now(UTC))
        logger.debug("Cached fundamentals", symbol=symbol, cache_key=cache_key)

    @override
    async def get_detailed_fundamentals(
        self,
        symbol: str,
        periods: int = 5,
        period_type: str = "annual",
    ) -> StockFundamentals:
        """Get comprehensive detailed fundamentals for a stock.

        This method aggregates financial statements, calculates ratios, and provides
        a complete fundamental analysis view normalized from yfinance data.

        Results are cached for the configured TTL to reduce API calls.
        """
        # Check cache first
        cached = self._get_cached_fundamentals(symbol, periods, period_type)
        if cached is not None:
            return cached

        try:
            if not YFINANCE_AVAILABLE:
                raise ImportError(
                    "yfinance is not installed. Install it with: pip install yfinance"
                )

            ticker = await asyncio.to_thread(lambda: yf.Ticker(symbol))

            # Get company info
            info = await asyncio.to_thread(lambda: ticker.info)

            # Get financial statements
            method_map = {
                "income_statement": (
                    "financials" if period_type == "annual" else "quarterly_financials"
                ),
                "balance_sheet": (
                    "balance_sheet" if period_type == "annual" else "quarterly_balance_sheet"
                ),
                "cash_flow": ("cashflow" if period_type == "annual" else "quarterly_cashflow"),
            }

            income_df: DataFrame = await asyncio.to_thread(
                lambda: getattr(ticker, method_map["income_statement"])
            )
            balance_df: DataFrame = await asyncio.to_thread(
                lambda: getattr(ticker, method_map["balance_sheet"])
            )
            cashflow_df: DataFrame = await asyncio.to_thread(
                lambda: getattr(ticker, method_map["cash_flow"])
            )

            # Check if all statements are empty (invalid symbol)
            if income_df.empty and balance_df.empty and cashflow_df.empty:
                raise DataProviderError(
                    self._provider_name,
                    "get_detailed_fundamentals",
                    f"Failed to fetch detailed fundamentals for {symbol}: "
                    "No financial data found. Symbol may be invalid.",
                )

            # Parse income statements
            income_statements: list[IncomeStatement] = []
            if not income_df.empty:
                for col in income_df.columns[:periods]:  # Limit to requested periods
                    period = self._parse_financial_statement_period(col, period_type)
                    if not period:
                        continue

                    # Extract values from DataFrame (yfinance uses row names as index)
                    # Convert to dict, handling NaN values
                    # Get the series for this column - use fillna to convert NaN to None
                    row_series = income_df[col]
                    # Convert NaN to None, preserve 0 and other values
                    income_row_dict: dict[str, Any] = {}
                    for idx in row_series.index:
                        value = row_series.loc[idx]
                        # Check if NaN (using pandas isnan if available, otherwise v != v)
                        if (
                            value is None
                            or isinstance(value, float)
                            and (value != value or (pd and pd.isna(value)))
                        ):
                            income_row_dict[idx] = None
                        else:
                            income_row_dict[idx] = value

                    income = IncomeStatement(
                        period=period,
                        total_revenue=self._safe_decimal(
                            income_row_dict.get("Total Revenue") or income_row_dict.get("Revenue")
                        ),
                        cost_of_revenue=self._safe_decimal(
                            income_row_dict.get("Cost Of Revenue")
                            or income_row_dict.get("Cost of Revenue")
                        ),
                        gross_profit=self._safe_decimal(income_row_dict.get("Gross Profit")),
                        operating_expenses=self._safe_decimal(
                            income_row_dict.get("Operating Expense")
                            or income_row_dict.get("Operating Expenses")
                        ),
                        operating_income=self._safe_decimal(
                            income_row_dict.get("Operating Income") or income_row_dict.get("EBIT")
                        ),
                        interest_expense=self._safe_decimal(
                            income_row_dict.get("Interest Expense")
                        ),
                        income_before_tax=self._safe_decimal(
                            income_row_dict.get("Income Before Tax")
                            or income_row_dict.get("Pretax Income")
                            or income_row_dict.get("Income Before Taxes")
                        ),
                        income_tax_expense=self._safe_decimal(
                            income_row_dict.get("Tax Provision")
                            or income_row_dict.get("Income Tax Expense")
                            or income_row_dict.get("Tax Expense")
                        ),
                        net_income=self._safe_decimal(income_row_dict.get("Net Income")),
                        earnings_per_share=self._safe_decimal(
                            income_row_dict.get("Basic EPS")
                            or income_row_dict.get("Earnings Per Share")
                        ),
                        diluted_eps=self._safe_decimal(income_row_dict.get("Diluted EPS")),
                        shares_outstanding=self._safe_int(
                            income_row_dict.get("Basic Average Shares")
                            or income_row_dict.get("Shares Outstanding")
                        ),
                        diluted_shares=self._safe_int(
                            income_row_dict.get("Diluted Average Shares")
                        ),
                        metadata={
                            "provider": self._provider_name,
                            "period_type": period_type,
                            "data_source": "yfinance",
                            "fiscal_year": str(period.fiscal_year),
                        },
                    )
                    income_statements.append(income)

            # Parse balance sheets
            balance_sheets: list[BalanceSheet] = []
            if not balance_df.empty:
                for col in balance_df.columns[:periods]:
                    period = self._parse_financial_statement_period(col, period_type)
                    if not period:
                        continue

                    # Convert to dict, handling NaN values
                    # Get the series for this column - use fillna to convert NaN to None
                    row_series = balance_df[col]
                    # Convert NaN to None, preserve 0 and other values
                    balance_row_dict: dict[str, Any] = {}
                    for idx in row_series.index:
                        value = row_series.loc[idx]
                        # Check if NaN (using pandas isnan if available, otherwise v != v)
                        if (
                            value is None
                            or isinstance(value, float)
                            and (value != value or (pd and pd.isna(value)))
                        ):
                            balance_row_dict[idx] = None
                        else:
                            balance_row_dict[idx] = value

                    # For short_term_debt, check Current Debt And Capital Lease Obligation
                    # and subtract Current Capital Lease Obligation if available
                    current_debt_and_lease = self._safe_decimal(
                        balance_row_dict.get("Current Debt And Capital Lease Obligation")
                    )
                    current_lease = self._safe_decimal(
                        balance_row_dict.get("Current Capital Lease Obligation")
                    )
                    if current_debt_and_lease is not None and current_lease is not None:
                        # Calculate pure debt by subtracting lease obligation
                        short_term_debt_value = current_debt_and_lease - current_lease
                        short_term_debt = (
                            short_term_debt_value if short_term_debt_value > 0 else None
                        )
                    else:
                        short_term_debt = self._safe_decimal(
                            balance_row_dict.get("Current Debt")
                            or balance_row_dict.get("Short Term Debt")
                            or balance_row_dict.get("ShortTerm Debt")
                            or balance_row_dict.get("Short-Term Debt")
                            or balance_row_dict.get("Current Portion Of Debt")
                        )

                    balance = BalanceSheet(
                        period=period,
                        cash_and_cash_equivalents=self._safe_decimal(
                            balance_row_dict.get("Cash And Cash Equivalents")
                            or balance_row_dict.get(
                                "Cash Cash Equivalents And Short Term Investments"
                            )
                        ),
                        short_term_investments=self._safe_decimal(
                            balance_row_dict.get("Other Short Term Investments")
                            or balance_row_dict.get("Short Term Investments")
                            or balance_row_dict.get("ShortTerm Investments")
                        ),
                        accounts_receivable=self._safe_decimal(
                            balance_row_dict.get("Net Receivables")
                            or balance_row_dict.get("Accounts Receivable")
                        ),
                        inventory=self._safe_decimal(balance_row_dict.get("Inventory")),
                        current_assets=self._safe_decimal(balance_row_dict.get("Current Assets")),
                        property_plant_equipment=self._safe_decimal(
                            balance_row_dict.get("Property Plant Equipment")
                            or balance_row_dict.get("Net PPE")
                        ),
                        long_term_investments=self._safe_decimal(
                            balance_row_dict.get("Investments And Advances")
                            or balance_row_dict.get("Investmentin Financial Assets")
                            or balance_row_dict.get("Long Term Investments")
                            or balance_row_dict.get("LongTerm Investments")
                        ),
                        total_assets=self._safe_decimal(balance_row_dict.get("Total Assets")),
                        accounts_payable=self._safe_decimal(
                            balance_row_dict.get("Accounts Payable")
                        ),
                        short_term_debt=short_term_debt,
                        current_liabilities=self._safe_decimal(
                            balance_row_dict.get("Current Liabilities")
                        ),
                        long_term_debt=self._safe_decimal(balance_row_dict.get("Long Term Debt")),
                        total_liabilities=self._safe_decimal(
                            balance_row_dict.get("Total Liabilities Net Minority Interest")
                            or balance_row_dict.get("Total Liabilities")
                            or balance_row_dict.get("Total Liab")
                        ),
                        common_stock=self._safe_decimal(balance_row_dict.get("Common Stock")),
                        retained_earnings=self._safe_decimal(
                            balance_row_dict.get("Retained Earnings")
                        ),
                        total_equity=self._safe_decimal(
                            balance_row_dict.get("Stockholders Equity")
                            or balance_row_dict.get("Total Equity")
                        ),
                        total_liabilities_and_equity=self._safe_decimal(
                            balance_row_dict.get("Total Liabilities And Equity")
                            or balance_row_dict.get("Total Liabilities And Stockholders Equity")
                            or balance_row_dict.get("Total Liab And Stock Equity")
                        ),
                        metadata={
                            "provider": self._provider_name,
                            "period_type": period_type,
                            "data_source": "yfinance",
                            "fiscal_year": str(period.fiscal_year),
                        },
                    )
                    balance_sheets.append(balance)

            # Parse cash flow statements
            cash_flow_statements: list[CashFlowStatement] = []
            if not cashflow_df.empty:
                for col in cashflow_df.columns[:periods]:
                    period = self._parse_financial_statement_period(col, period_type)
                    if not period:
                        continue

                    # Convert to dict, handling NaN values
                    # Get the series for this column - use fillna to convert NaN to None
                    row_series = cashflow_df[col]
                    # Convert NaN to None, preserve 0 and other values
                    cashflow_row_dict: dict[str, Any] = {}
                    for idx in row_series.index:
                        value = row_series.loc[idx]
                        # Check if NaN (using pandas isnan if available, otherwise v != v)
                        if (
                            value is None
                            or isinstance(value, float)
                            and (value != value or (pd and pd.isna(value)))
                        ):
                            cashflow_row_dict[idx] = None
                        else:
                            cashflow_row_dict[idx] = value

                    operating_cf = self._safe_decimal(
                        cashflow_row_dict.get("Operating Cash Flow")
                        or cashflow_row_dict.get("Total Cash From Operating Activities")
                    )
                    investing_cf = self._safe_decimal(
                        cashflow_row_dict.get("Investing Cash Flow")
                        or cashflow_row_dict.get("Total Cashflows From Investing Activities")
                    )
                    financing_cf = self._safe_decimal(
                        cashflow_row_dict.get("Financing Cash Flow")
                        or cashflow_row_dict.get("Total Cash From Financing Activities")
                    )

                    # Calculate free cash flow
                    fcf = None
                    if operating_cf:
                        capex = self._safe_decimal(
                            cashflow_row_dict.get("Capital Expenditures")
                            or cashflow_row_dict.get("Capital Expenditure")
                        )
                        fcf = (
                            operating_cf - abs(capex) if capex else operating_cf
                        )  # CapEx is typically negative

                    cashflow = CashFlowStatement(
                        period=period,
                        net_income=self._safe_decimal(
                            cashflow_row_dict.get("Net Income")
                            or cashflow_row_dict.get("Net Income From Continuing Operations")
                            or cashflow_row_dict.get(
                                "Net Income From Continuing Operations Including Portion Attributable To Noncontrolling Interest"
                            )
                        ),
                        depreciation_amortization=self._safe_decimal(
                            cashflow_row_dict.get("Depreciation And Amortization")
                            or cashflow_row_dict.get("Depreciation Amortization Depletion")
                            or cashflow_row_dict.get("Depreciation")
                            or cashflow_row_dict.get("Depreciation & Amortization")
                        ),
                        stock_based_compensation=self._safe_decimal(
                            cashflow_row_dict.get("Stock Based Compensation")
                        ),
                        changes_in_working_capital=self._safe_decimal(
                            cashflow_row_dict.get("Change In Working Capital")
                        ),
                        operating_cash_flow=operating_cf,
                        capital_expenditures=self._safe_decimal(
                            cashflow_row_dict.get("Capital Expenditures")
                            or cashflow_row_dict.get("Capital Expenditure")
                        ),
                        investments=self._safe_decimal(
                            cashflow_row_dict.get("Net Investment Purchase And Sale")
                            or cashflow_row_dict.get("Purchase Of Investment")
                            or cashflow_row_dict.get("Sale Of Investment")
                            or cashflow_row_dict.get("Investments")
                            or cashflow_row_dict.get("Investment")
                        ),
                        investing_cash_flow=investing_cf,
                        debt_issued=self._safe_decimal(
                            cashflow_row_dict.get("Long Term Debt Issuance")
                            or cashflow_row_dict.get("Issuance Of Debt")
                            or cashflow_row_dict.get("Debt Issuance")
                            or cashflow_row_dict.get("Issuance Of Long Term Debt")
                            or cashflow_row_dict.get("Proceeds From Issuance Of Debt")
                            or cashflow_row_dict.get("Proceeds From Debt")
                            or cashflow_row_dict.get(
                                "Long Term Debt And Capital Securities Net Issuance"
                            )
                        ),
                        debt_repaid=self._safe_decimal(
                            cashflow_row_dict.get("Repayment Of Debt")
                            or cashflow_row_dict.get("Debt Repayment")
                            or cashflow_row_dict.get("Long Term Debt Repayment")
                        ),
                        dividends_paid=self._safe_decimal(
                            cashflow_row_dict.get("Cash Dividends Paid")
                            or cashflow_row_dict.get("Common Stock Dividend Paid")
                            or cashflow_row_dict.get("Dividends Paid")
                            or cashflow_row_dict.get("Common Stock Dividends Paid")
                        ),
                        share_repurchases=self._safe_decimal(
                            cashflow_row_dict.get("Repurchase Of Capital Stock")
                            or cashflow_row_dict.get("Common Stock Payments")
                            or cashflow_row_dict.get("Repurchase Of Stock")
                            or cashflow_row_dict.get("Common Stock Repurchased")
                        ),
                        share_issuance=self._safe_decimal(
                            cashflow_row_dict.get("Proceeds From Stock Option Exercised")
                            or cashflow_row_dict.get("Net Common Stock Issuance")
                            or cashflow_row_dict.get("Issuance Of Stock")
                            or cashflow_row_dict.get("Common Stock Issuance")
                        ),
                        financing_cash_flow=financing_cf,
                        net_change_in_cash=self._safe_decimal(
                            cashflow_row_dict.get("Changes In Cash")
                            or cashflow_row_dict.get("Change In Cash")
                            or cashflow_row_dict.get("Net Change In Cash")
                            or cashflow_row_dict.get("Net Change In Cash And Cash Equivalents")
                        ),
                        free_cash_flow=fcf,
                        metadata={
                            "provider": self._provider_name,
                            "period_type": period_type,
                            "data_source": "yfinance",
                            "fiscal_year": str(period.fiscal_year),
                            "fcf_calculated": "true" if fcf else "false",
                        },
                    )
                    cash_flow_statements.append(cashflow)

            # Get most recent statements for ratio calculation
            latest_income = income_statements[0] if income_statements else None
            latest_balance = balance_sheets[0] if balance_sheets else None
            latest_cashflow = cash_flow_statements[0] if cash_flow_statements else None

            # Get market data from info
            market_cap = self._safe_decimal(info.get("marketCap"))
            current_price = self._safe_decimal(
                info.get("currentPrice") or info.get("regularMarketPrice")
            )
            shares_outstanding = self._safe_int(info.get("sharesOutstanding"))
            float_shares = self._safe_int(info.get("floatShares"))
            enterprise_value = self._safe_decimal(info.get("enterpriseValue"))

            # Calculate ratios (pass historical statements for growth rate calculations)
            ratios = self._calculate_ratios(
                latest_income,
                latest_balance,
                latest_cashflow,
                market_cap,
                current_price,
                shares_outstanding,
                enterprise_value=enterprise_value,
                income_statements=income_statements if income_statements else None,
                cash_flow_statements=cash_flow_statements if cash_flow_statements else None,
            )

            # Build StockFundamentals entity
            # Build metadata with useful company and data quality information
            fundamentals_metadata: dict[str, str] = {
                "provider": self._provider_name,
                "data_source": "yfinance",
                "periods_requested": str(periods),
                "period_type": period_type,
                "income_statements_count": str(len(income_statements)),
                "balance_sheets_count": str(len(balance_sheets)),
                "cash_flow_statements_count": str(len(cash_flow_statements)),
            }
            # Add additional company info if available
            if info.get("website"):
                fundamentals_metadata["website"] = str(info.get("website"))
            if info.get("exchange"):
                fundamentals_metadata["exchange"] = str(info.get("exchange"))
            if info.get("country"):
                fundamentals_metadata["country"] = str(info.get("country"))

            fundamentals = StockFundamentals(
                symbol=symbol.upper(),
                company_name=info.get("longName") or info.get("shortName"),
                sector=info.get("sector"),
                industry=info.get("industry"),
                income_statements=income_statements,
                balance_sheets=balance_sheets,
                cash_flow_statements=cash_flow_statements,
                ratios=ratios,
                market_cap=market_cap,
                enterprise_value=enterprise_value,
                current_price=current_price,
                shares_outstanding=shares_outstanding,
                float_shares=float_shares,
                provider=self._provider_name,
                data_as_of=datetime.now(UTC),
                fiscal_year_end=(
                    info.get("fiscalYearEnd")
                    or info.get("fiscalYearEndDate")
                    or info.get("fiscalYearEndMonth")
                ),
                currency=info.get("currency"),
                metadata=fundamentals_metadata,
            )

            logger.info(
                "Fetched detailed fundamentals",
                symbol=symbol,
                periods=len(income_statements),
                provider=self._provider_name,
            )

            # Cache the results before returning
            self._cache_fundamentals(symbol, periods, period_type, fundamentals)

            return fundamentals

        except Exception as e:
            logger.error(
                "Failed to fetch detailed fundamentals",
                symbol=symbol,
                error=str(e),
            )
            raise DataProviderError(
                self._provider_name,
                "get_detailed_fundamentals",
                f"Failed to fetch detailed fundamentals for {symbol}: {e}",
            ) from e
