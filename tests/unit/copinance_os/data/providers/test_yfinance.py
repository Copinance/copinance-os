"""Unit tests for yfinance data provider implementation."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copinance_os.data.providers import yfinance as yfinance_module
from copinance_os.data.providers.yfinance import (
    YFinanceFundamentalProvider,
    YFinanceMarketProvider,
)
from copinance_os.domain.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    FinancialRatios,
    FinancialStatementPeriod,
    IncomeStatement,
    StockFundamentals,
)
from copinance_os.domain.models.market import MarketDataPoint


@pytest.mark.unit
def test_select_options_expiration_prefers_first_on_or_after_as_of() -> None:
    pick = yfinance_module._select_options_expiration_string
    avail = ["2026-03-27", "2026-04-03", "2026-04-10"]
    assert pick(avail, None, as_of=date(2026, 3, 28)) == "2026-04-03"


@pytest.mark.unit
def test_select_options_expiration_explicit_wins() -> None:
    pick = yfinance_module._select_options_expiration_string
    assert pick(["2026-04-03"], "2026-04-03", as_of=date(2026, 3, 28)) == "2026-04-03"


@pytest.mark.unit
def test_select_options_expiration_all_in_the_past_falls_back_to_last() -> None:
    pick = yfinance_module._select_options_expiration_string
    assert pick(["2026-03-20", "2026-03-27"], None, as_of=date(2026, 4, 1)) == "2026-03-27"


@pytest.mark.unit
def test_yahoo_option_implied_volatility_percent_to_sigma() -> None:
    """yahoo sometimes returns IV as percent points; QuantLib needs σ as a fraction."""
    norm = yfinance_module._yahoo_option_implied_volatility_to_sigma
    assert norm(None) is None
    assert norm(Decimal("0.25")) == Decimal("0.25")
    assert norm(Decimal("1")) == Decimal("1")
    assert norm(Decimal("13.671876455078125")) == Decimal("0.13671876455078125")
    assert norm(Decimal("6.87500140625")) == Decimal("0.0687500140625")


@pytest.mark.unit
class TestYFinanceMarketProvider:
    """Test YFinanceMarketProvider."""

    def test_initialization(self) -> None:
        """Test provider initialization."""
        with patch("copinance_os.data.providers.yfinance.logger") as mock_logger:
            provider = YFinanceMarketProvider()
            assert provider._provider_name == "yfinance"
            mock_logger.info.assert_called_once()

    def test_get_provider_name(self) -> None:
        """Test getting provider name."""
        provider = YFinanceMarketProvider()
        assert provider.get_provider_name() == "yfinance"

    @pytest.mark.asyncio
    async def test_is_available_when_yfinance_not_available(self) -> None:
        """Test is_available returns False when yfinance is not installed."""
        with patch("copinance_os.data.providers.yfinance.YFINANCE_AVAILABLE", False):
            provider = YFinanceMarketProvider()
            result = await provider.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_is_available_when_yfinance_available(self) -> None:
        """Test is_available returns True when yfinance is available."""
        with (
            patch("copinance_os.data.providers.yfinance.YFINANCE_AVAILABLE", True),
            patch("copinance_os.data.providers.yfinance.yf") as mock_yf,
            patch("asyncio.to_thread", new=AsyncMock(return_value={"test": "data"})),
        ):
            mock_ticker = MagicMock()
            mock_ticker.info = {"test": "data"}
            mock_yf.Ticker.return_value = mock_ticker

            provider = YFinanceMarketProvider()
            result = await provider.is_available()
            assert result is True

    @pytest.mark.asyncio
    async def test_is_available_handles_exception(self) -> None:
        """Test is_available handles exceptions gracefully."""
        with (
            patch("copinance_os.data.providers.yfinance.YFINANCE_AVAILABLE", True),
            patch("copinance_os.data.providers.yfinance.yf"),
            patch("copinance_os.data.providers.yfinance.logger") as mock_logger,
            patch("asyncio.to_thread", new=AsyncMock(side_effect=Exception("Test error"))),
        ):
            provider = YFinanceMarketProvider()
            result = await provider.is_available()
            assert result is False
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_quote_success(self) -> None:
        """Test getting a quote successfully."""
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "currentPrice": 150.0,
            "previousClose": 149.0,
            "open": 150.5,
            "dayHigh": 151.0,
            "dayLow": 149.5,
            "volume": 1000000,
            "marketCap": 2500000000,
            "currency": "USD",
            "exchange": "NASDAQ",
        }
        mock_hist = MagicMock()
        mock_hist.empty = True

        with patch(
            "asyncio.to_thread",
            new=AsyncMock(side_effect=[mock_ticker, mock_ticker.info, mock_hist]),
        ):
            provider = YFinanceMarketProvider()
            quote = await provider.get_quote("AAPL")

            assert quote["symbol"] == "AAPL"
            assert quote["current_price"] == Decimal("150.0")
            assert quote["previous_close"] == Decimal("149.0")
            assert quote["open"] == Decimal("150.5")
            assert quote["high"] == Decimal("151.0")
            assert quote["low"] == Decimal("149.5")
            assert quote["volume"] == 1000000
            assert quote["market_cap"] == 2500000000
            assert quote["currency"] == "USD"
            assert quote["exchange"] == "NASDAQ"
            assert "timestamp" in quote

    @pytest.mark.asyncio
    async def test_get_quote_with_history(self) -> None:
        """Test getting a quote with history data."""
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "currentPrice": 150.0,
            "previousClose": 149.0,
            "open": 150.5,
            "dayHigh": 151.0,
            "dayLow": 149.5,
            "volume": 1000000,
        }
        mock_hist = MagicMock()
        mock_hist.empty = False
        mock_row = MagicMock()
        mock_row.__getitem__.return_value = 152.0
        mock_hist.iloc = MagicMock()
        mock_hist.iloc.__getitem__.return_value = mock_row
        mock_row.__getitem__ = MagicMock(
            side_effect=lambda key: 2000000 if key == "Volume" else 152.0
        )

        with patch(
            "asyncio.to_thread",
            new=AsyncMock(side_effect=[mock_ticker, mock_ticker.info, mock_hist]),
        ):
            provider = YFinanceMarketProvider()
            quote = await provider.get_quote("AAPL")

            assert quote["current_price"] == Decimal("152.0")
            assert quote["volume"] == 2000000

    @pytest.mark.asyncio
    async def test_get_quote_handles_exception(self) -> None:
        """Test get_quote handles exceptions."""
        with (
            patch("copinance_os.data.providers.yfinance.logger") as mock_logger,
            patch("asyncio.to_thread", new=AsyncMock(side_effect=Exception("API error"))),
        ):
            provider = YFinanceMarketProvider()
            with pytest.raises(ValueError, match="Failed to fetch quote"):
                await provider.get_quote("AAPL")
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_historical_data_success(self) -> None:
        """Test getting historical data successfully."""
        mock_ticker = MagicMock()
        mock_df = MagicMock()
        mock_df.empty = False
        mock_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        mock_timestamp_obj = MagicMock()
        mock_timestamp_obj.to_pydatetime.return_value = mock_timestamp
        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(
            side_effect=lambda key: {
                "Open": 100.0,
                "Close": 101.0,
                "High": 102.0,
                "Low": 99.0,
                "Volume": 1000000,
            }.get(key, 0)
        )
        mock_df.iterrows.return_value = [(mock_timestamp_obj, mock_row)]

        with (
            patch("copinance_os.data.providers.yfinance.YFINANCE_AVAILABLE", True),
            patch("asyncio.to_thread", new=AsyncMock(side_effect=[mock_ticker, mock_df])),
        ):
            provider = YFinanceMarketProvider()
            start_date = datetime(2024, 1, 1)
            end_date = datetime(2024, 1, 31)
            result = await provider.get_historical_data("AAPL", start_date, end_date)

            assert len(result) == 1
            assert isinstance(result[0], MarketDataPoint)
            assert result[0].symbol == "AAPL"
            assert result[0].open_price == Decimal("100.0")
            assert result[0].close_price == Decimal("101.0")

    @pytest.mark.asyncio
    async def test_get_historical_data_empty(self) -> None:
        """Test getting historical data when empty."""
        mock_ticker = MagicMock()
        mock_df = MagicMock()
        mock_df.empty = True

        with (
            patch("copinance_os.data.providers.yfinance.YFINANCE_AVAILABLE", True),
            patch("copinance_os.data.providers.yfinance.logger") as mock_logger,
            patch("asyncio.to_thread", new=AsyncMock(side_effect=[mock_ticker, mock_df])),
        ):
            provider = YFinanceMarketProvider()
            start_date = datetime(2024, 1, 1)
            end_date = datetime(2024, 1, 31)
            result = await provider.get_historical_data("AAPL", start_date, end_date)

            assert result == []
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_historical_data_yfinance_not_available(self) -> None:
        """Test get_historical_data raises error when yfinance not available."""
        with patch("copinance_os.data.providers.yfinance.YFINANCE_AVAILABLE", False):
            provider = YFinanceMarketProvider()
            start_date = datetime(2024, 1, 1)
            end_date = datetime(2024, 1, 31)
            with pytest.raises(ValueError, match="yfinance is not installed"):
                await provider.get_historical_data("AAPL", start_date, end_date)

    @pytest.mark.asyncio
    async def test_get_historical_data_handles_exception(self) -> None:
        """Test get_historical_data handles exceptions."""
        with (
            patch("copinance_os.data.providers.yfinance.YFINANCE_AVAILABLE", True),
            patch("copinance_os.data.providers.yfinance.logger") as mock_logger,
            patch("asyncio.to_thread", new=AsyncMock(side_effect=Exception("API error"))),
        ):
            provider = YFinanceMarketProvider()
            start_date = datetime(2024, 1, 1)
            end_date = datetime(2024, 1, 31)
            with pytest.raises(ValueError, match="Failed to fetch historical data"):
                await provider.get_historical_data("AAPL", start_date, end_date)
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_intraday_data_success(self) -> None:
        """Test getting intraday data successfully."""
        mock_ticker = MagicMock()
        mock_df = MagicMock()
        mock_df.empty = False
        mock_timestamp = datetime(2024, 1, 1, tzinfo=UTC)
        mock_timestamp_obj = MagicMock()
        mock_timestamp_obj.to_pydatetime.return_value = mock_timestamp
        mock_row = MagicMock()
        mock_row.__getitem__ = MagicMock(
            side_effect=lambda key: {
                "Open": 100.0,
                "Close": 101.0,
                "High": 102.0,
                "Low": 99.0,
                "Volume": 1000000,
            }.get(key, 0)
        )
        mock_df.iterrows.return_value = [(mock_timestamp_obj, mock_row)]

        with (
            patch("copinance_os.data.providers.yfinance.YFINANCE_AVAILABLE", True),
            patch("asyncio.to_thread", new=AsyncMock(side_effect=[mock_ticker, mock_df])),
        ):
            provider = YFinanceMarketProvider()
            result = await provider.get_intraday_data("AAPL", interval="1min")

            assert len(result) == 1
            assert isinstance(result[0], MarketDataPoint)
            assert result[0].symbol == "AAPL"
            assert "intraday" in result[0].metadata["data_type"]

    @pytest.mark.asyncio
    async def test_get_intraday_data_yfinance_not_available(self) -> None:
        """Test get_intraday_data raises error when yfinance not available."""
        with patch("copinance_os.data.providers.yfinance.YFINANCE_AVAILABLE", False):
            provider = YFinanceMarketProvider()
            with pytest.raises(ValueError, match="yfinance is not installed"):
                await provider.get_intraday_data("AAPL")

    @pytest.mark.asyncio
    async def test_search_stocks_success(self) -> None:
        """Test searching stocks successfully."""
        mock_search = MagicMock()
        mock_search.quotes = [
            {
                "symbol": "AAPL",
                "longname": "Apple Inc.",
                "exchange": "NASDAQ",
                "quoteType": "EQUITY",
            },
            {
                "symbol": "MSFT",
                "shortname": "Microsoft",
                "exchange": "NASDAQ",
                "quoteType": "ETF",
            },
        ]

        with (
            patch("copinance_os.data.providers.yfinance.YFINANCE_AVAILABLE", True),
            patch("asyncio.to_thread", new=AsyncMock(return_value=mock_search)),
        ):
            provider = YFinanceMarketProvider()
            result = await provider.search_instruments("Apple", limit=10)

            assert len(result) == 2
            assert result[0]["symbol"] == "AAPL"
            assert result[0]["name"] == "Apple Inc."
            assert result[1]["symbol"] == "MSFT"

    @pytest.mark.asyncio
    async def test_search_instruments_no_results(self) -> None:
        """Test searching instruments with no results."""
        mock_search = MagicMock()
        mock_search.quotes = []

        with (
            patch("copinance_os.data.providers.yfinance.YFINANCE_AVAILABLE", True),
            patch("copinance_os.data.providers.yfinance.logger") as mock_logger,
            patch("asyncio.to_thread", new=AsyncMock(return_value=mock_search)),
        ):
            provider = YFinanceMarketProvider()
            result = await provider.search_instruments("NONEXISTENT", limit=10)

            assert result == []
            mock_logger.debug.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_instruments_filters_by_quote_type(self) -> None:
        """Test that search_instruments filters out non-equity types."""
        mock_search = MagicMock()
        mock_search.quotes = [
            {
                "symbol": "AAPL",
                "longname": "Apple Inc.",
                "exchange": "NASDAQ",
                "quoteType": "EQUITY",
            },
            {
                "symbol": "BOND",
                "longname": "Bond",
                "exchange": "NYSE",
                "quoteType": "BOND",
            },
        ]

        with (
            patch("copinance_os.data.providers.yfinance.YFINANCE_AVAILABLE", True),
            patch("asyncio.to_thread", new=AsyncMock(return_value=mock_search)),
        ):
            provider = YFinanceMarketProvider()
            result = await provider.search_instruments("test", limit=10)

            assert len(result) == 1
            assert result[0]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_search_instruments_handles_exception(self) -> None:
        """Test search_instruments handles exceptions gracefully."""
        with (
            patch("copinance_os.data.providers.yfinance.YFINANCE_AVAILABLE", True),
            patch("copinance_os.data.providers.yfinance.logger") as mock_logger,
            patch("asyncio.to_thread", new=AsyncMock(side_effect=Exception("API error"))),
        ):
            provider = YFinanceMarketProvider()
            result = await provider.search_instruments("test", limit=10)

            assert result == []
            mock_logger.warning.assert_called_once()


@pytest.mark.unit
class TestYFinanceFundamentalProvider:
    """Test YFinanceFundamentalProvider."""

    def test_initialization(self) -> None:
        """Test provider initialization."""
        with patch("copinance_os.data.providers.yfinance.logger") as mock_logger:
            provider = YFinanceFundamentalProvider(cache_ttl_seconds=1800)
            assert provider._provider_name == "yfinance"
            assert provider._cache_ttl_seconds == 1800
            assert provider._cache == {}
            mock_logger.info.assert_called_once()

    def test_initialization_default_cache_ttl(self) -> None:
        """Test provider initialization with default cache TTL."""
        provider = YFinanceFundamentalProvider()
        assert provider._cache_ttl_seconds == 3600

    def test_get_provider_name(self) -> None:
        """Test getting provider name."""
        provider = YFinanceFundamentalProvider()
        assert provider.get_provider_name() == "yfinance"

    @pytest.mark.asyncio
    async def test_is_available_when_yfinance_not_available(self) -> None:
        """Test is_available returns False when yfinance is not installed."""
        with patch("copinance_os.data.providers.yfinance.YFINANCE_AVAILABLE", False):
            provider = YFinanceFundamentalProvider()
            result = await provider.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_is_available_when_yfinance_available(self) -> None:
        """Test is_available returns True when yfinance is available."""
        with (
            patch("copinance_os.data.providers.yfinance.YFINANCE_AVAILABLE", True),
            patch("copinance_os.data.providers.yfinance.yf") as mock_yf,
            patch("asyncio.to_thread", new=AsyncMock(return_value={"test": "data"})),
        ):
            mock_ticker = MagicMock()
            mock_ticker.info = {"test": "data"}
            mock_yf.Ticker.return_value = mock_ticker

            provider = YFinanceFundamentalProvider()
            result = await provider.is_available()
            assert result is True

    @pytest.mark.asyncio
    async def test_get_financial_statements_success(self) -> None:
        """Test getting financial statements successfully."""
        mock_ticker = MagicMock()
        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.to_dict.return_value = {"2023-12-31": {"Revenue": 1000000.0}}
        mock_ticker.financials = mock_df

        with (
            patch("copinance_os.data.providers.yfinance.YFINANCE_AVAILABLE", True),
            patch("asyncio.to_thread", new=AsyncMock(side_effect=[mock_ticker, mock_df])),
        ):
            provider = YFinanceFundamentalProvider()
            result = await provider.get_financial_statements("AAPL", "income_statement", "annual")

            assert result["symbol"] == "AAPL"
            assert result["statement_type"] == "income_statement"
            assert result["period"] == "annual"
            assert "data" in result

    @pytest.mark.asyncio
    async def test_get_financial_statements_empty(self) -> None:
        """Test getting financial statements when empty."""
        mock_ticker = MagicMock()
        mock_df = MagicMock()
        mock_df.empty = True
        mock_ticker.financials = mock_df

        with (
            patch("copinance_os.data.providers.yfinance.YFINANCE_AVAILABLE", True),
            patch("copinance_os.data.providers.yfinance.logger") as mock_logger,
            patch("asyncio.to_thread", new=AsyncMock(side_effect=[mock_ticker, mock_df])),
        ):
            provider = YFinanceFundamentalProvider()
            result = await provider.get_financial_statements("AAPL", "income_statement", "annual")

            assert result["symbol"] == "AAPL"
            assert result["data"] == {}
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_financial_statements_invalid_type(self) -> None:
        """Test getting financial statements with invalid type."""
        mock_ticker = MagicMock()

        with (
            patch("copinance_os.data.providers.yfinance.YFINANCE_AVAILABLE", True),
            patch("asyncio.to_thread", new=AsyncMock(return_value=mock_ticker)),
        ):
            provider = YFinanceFundamentalProvider()
            with pytest.raises(ValueError, match="Invalid statement_type"):
                await provider.get_financial_statements("AAPL", "invalid_type", "annual")

    @pytest.mark.asyncio
    async def test_get_sec_filings(self) -> None:
        """Test getting SEC filings (returns empty list)."""
        with patch("copinance_os.data.providers.yfinance.logger") as mock_logger:
            provider = YFinanceFundamentalProvider()
            result = await provider.get_sec_filings("AAPL", ["10-K"], limit=10)

            assert result == []
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_earnings_transcripts(self) -> None:
        """Test getting earnings transcripts (returns empty list)."""
        with patch("copinance_os.data.providers.yfinance.logger") as mock_logger:
            provider = YFinanceFundamentalProvider()
            result = await provider.get_earnings_transcripts("AAPL", limit=4)

            assert result == []
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_esg_metrics_success(self) -> None:
        """Test getting ESG metrics successfully."""
        mock_ticker = MagicMock()
        mock_ticker.info = {"esgScores": {"environment": 75, "social": 80, "governance": 70}}

        with patch("asyncio.to_thread", new=AsyncMock(side_effect=[mock_ticker, mock_ticker.info])):
            provider = YFinanceFundamentalProvider()
            result = await provider.get_esg_metrics("AAPL")

            assert result["symbol"] == "AAPL"
            assert "scores" in result
            assert result["scores"]["environment"] == 75

    @pytest.mark.asyncio
    async def test_get_esg_metrics_no_data(self) -> None:
        """Test getting ESG metrics when no data available."""
        mock_ticker = MagicMock()
        mock_ticker.info = {}

        with (
            patch("copinance_os.data.providers.yfinance.logger"),
            patch("asyncio.to_thread", new=AsyncMock(side_effect=[mock_ticker, mock_ticker.info])),
        ):
            provider = YFinanceFundamentalProvider()
            result = await provider.get_esg_metrics("AAPL")

            assert result["symbol"] == "AAPL"
            assert "scores" not in result

    @pytest.mark.asyncio
    async def test_get_esg_metrics_handles_exception(self) -> None:
        """Test get_esg_metrics handles exceptions."""
        with (
            patch("copinance_os.data.providers.yfinance.logger") as mock_logger,
            patch("asyncio.to_thread", new=AsyncMock(side_effect=Exception("API error"))),
        ):
            provider = YFinanceFundamentalProvider()
            result = await provider.get_esg_metrics("AAPL")

            assert result["symbol"] == "AAPL"
            assert "error" in result
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_insider_trading(self) -> None:
        """Test getting insider trading (returns empty list)."""
        with patch("copinance_os.data.providers.yfinance.logger") as mock_logger:
            provider = YFinanceFundamentalProvider()
            result = await provider.get_insider_trading("AAPL", lookback_days=90)

            assert result == []
            mock_logger.warning.assert_called_once()

    def test_safe_decimal_with_none(self) -> None:
        """Test _safe_decimal with None."""
        provider = YFinanceFundamentalProvider()
        assert provider._safe_decimal(None) is None

    def test_safe_decimal_with_int(self) -> None:
        """Test _safe_decimal with int."""
        provider = YFinanceFundamentalProvider()
        result = provider._safe_decimal(100)
        assert result == Decimal("100")

    def test_safe_decimal_with_float(self) -> None:
        """Test _safe_decimal with float."""
        provider = YFinanceFundamentalProvider()
        result = provider._safe_decimal(100.5)
        assert result == Decimal("100.5")

    def test_safe_decimal_with_nan(self) -> None:
        """Test _safe_decimal with NaN."""
        provider = YFinanceFundamentalProvider()

        result = provider._safe_decimal(float("nan"))
        assert result is None

    def test_safe_decimal_with_string(self) -> None:
        """Test _safe_decimal with string."""
        provider = YFinanceFundamentalProvider()
        result = provider._safe_decimal("100.5")
        assert result == Decimal("100.5")

    def test_safe_decimal_with_invalid_string(self) -> None:
        """Test _safe_decimal with invalid string."""
        provider = YFinanceFundamentalProvider()
        assert provider._safe_decimal("nan") is None
        assert provider._safe_decimal("none") is None
        assert provider._safe_decimal("") is None

    def test_safe_int_with_none(self) -> None:
        """Test _safe_int with None."""
        provider = YFinanceFundamentalProvider()
        assert provider._safe_int(None) is None

    def test_safe_int_with_int(self) -> None:
        """Test _safe_int with int."""
        provider = YFinanceFundamentalProvider()
        result = provider._safe_int(100)
        assert result == 100

    def test_safe_int_with_float(self) -> None:
        """Test _safe_int with float."""
        provider = YFinanceFundamentalProvider()
        result = provider._safe_int(100.7)
        assert result == 100

    def test_safe_int_with_nan(self) -> None:
        """Test _safe_int with NaN."""
        provider = YFinanceFundamentalProvider()

        result = provider._safe_int(float("nan"))
        assert result is None

    def test_safe_int_with_string(self) -> None:
        """Test _safe_int with string."""
        provider = YFinanceFundamentalProvider()
        result = provider._safe_int("100")
        assert result == 100

    def test_parse_financial_statement_period_with_datetime(self) -> None:
        """Test _parse_financial_statement_period with datetime."""
        provider = YFinanceFundamentalProvider()
        period_date = datetime(2024, 3, 31)
        result = provider._parse_financial_statement_period(period_date, "quarterly")

        assert result is not None
        assert result.fiscal_year == 2024
        assert result.fiscal_quarter == 1
        assert result.period_type == "quarterly"

    def test_parse_financial_statement_period_with_string(self) -> None:
        """Test _parse_financial_statement_period with string."""
        provider = YFinanceFundamentalProvider()
        result = provider._parse_financial_statement_period("2024-12-31", "annual")

        assert result is not None
        assert result.fiscal_year == 2024
        assert result.period_type == "annual"

    def test_parse_financial_statement_period_invalid(self) -> None:
        """Test _parse_financial_statement_period with invalid input."""
        provider = YFinanceFundamentalProvider()
        result = provider._parse_financial_statement_period("invalid", "annual")
        assert result is None

    def test_get_cache_key(self) -> None:
        """Test _get_cache_key generation."""
        provider = YFinanceFundamentalProvider()
        key = provider._get_cache_key("AAPL", 5, "annual")
        assert key == "AAPL:5:annual"

    def test_get_cached_fundamentals_not_cached(self) -> None:
        """Test _get_cached_fundamentals when not cached."""
        provider = YFinanceFundamentalProvider()
        result = provider._get_cached_fundamentals("AAPL", 5, "annual")
        assert result is None

    def test_get_cached_fundamentals_cached(self) -> None:
        """Test _get_cached_fundamentals when cached."""
        with patch("copinance_os.data.providers.yfinance.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, tzinfo=UTC)
            provider = YFinanceFundamentalProvider()
            fundamentals = StockFundamentals(
                symbol="AAPL",
                company_name="Apple Inc.",
                income_statements=[],
                balance_sheets=[],
                cash_flow_statements=[],
                ratios=FinancialRatios(),
                provider="yfinance",
                data_as_of=datetime(2024, 1, 1, tzinfo=UTC),
            )
            provider._cache_fundamentals("AAPL", 5, "annual", fundamentals)
            result = provider._get_cached_fundamentals("AAPL", 5, "annual")
            assert result is not None
            assert result.symbol == "AAPL"

    def test_get_cached_fundamentals_expired(self) -> None:
        """Test _get_cached_fundamentals when cache expired."""
        with patch("copinance_os.data.providers.yfinance.datetime") as mock_datetime:
            # Set initial time
            initial_time = datetime(2024, 1, 1, tzinfo=UTC)
            mock_datetime.now.return_value = initial_time
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            provider = YFinanceFundamentalProvider(cache_ttl_seconds=1)
            fundamentals = StockFundamentals(
                symbol="AAPL",
                company_name="Apple Inc.",
                income_statements=[],
                balance_sheets=[],
                cash_flow_statements=[],
                ratios=FinancialRatios(),
                provider="yfinance",
                data_as_of=datetime(2024, 1, 1, tzinfo=UTC),
            )
            provider._cache_fundamentals("AAPL", 5, "annual", fundamentals)

            # Advance time by 2 seconds (past TTL)
            expired_time = initial_time + timedelta(seconds=2)
            mock_datetime.now.return_value = expired_time

            result = provider._get_cached_fundamentals("AAPL", 5, "annual")
            assert result is None

    def test_cache_fundamentals(self) -> None:
        """Test _cache_fundamentals."""
        with patch("copinance_os.data.providers.yfinance.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, tzinfo=UTC)
            provider = YFinanceFundamentalProvider()
            fundamentals = StockFundamentals(
                symbol="AAPL",
                company_name="Apple Inc.",
                income_statements=[],
                balance_sheets=[],
                cash_flow_statements=[],
                ratios=FinancialRatios(),
                provider="yfinance",
                data_as_of=datetime(2024, 1, 1, tzinfo=UTC),
            )
            provider._cache_fundamentals("AAPL", 5, "annual", fundamentals)
            assert "AAPL:5:annual" in provider._cache

    def test_calculate_ratios_with_income_and_balance(self) -> None:
        """Test _calculate_ratios with income statement and balance sheet."""
        provider = YFinanceFundamentalProvider()
        period = FinancialStatementPeriod(
            period_end_date=datetime(2024, 12, 31),
            period_type="annual",
            fiscal_year=2024,
        )
        income = IncomeStatement(
            period=period,
            total_revenue=Decimal("1000000"),
            gross_profit=Decimal("400000"),
            operating_income=Decimal("200000"),
            net_income=Decimal("150000"),
            earnings_per_share=Decimal("5.0"),
        )
        balance = BalanceSheet(
            period=period,
            total_assets=Decimal("5000000"),
            total_equity=Decimal("3000000"),
            current_assets=Decimal("1000000"),
            current_liabilities=Decimal("500000"),
            cash_and_cash_equivalents=Decimal("200000"),
            accounts_receivable=Decimal("300000"),
            short_term_debt=Decimal("100000"),
            long_term_debt=Decimal("1500000"),
        )

        ratios = provider._calculate_ratios(
            income=income,
            balance=balance,
            cashflow=None,
            market_cap=None,
            current_price=Decimal("50.0"),
            shares_outstanding=30000000,
        )

        assert ratios is not None
        assert ratios.gross_margin is not None
        assert ratios.operating_margin is not None
        assert ratios.net_margin is not None
        assert ratios.current_ratio is not None
        assert ratios.debt_to_equity is not None

    def test_calculate_ratios_with_cashflow(self) -> None:
        """Test _calculate_ratios with cash flow statement."""
        provider = YFinanceFundamentalProvider()
        period = FinancialStatementPeriod(
            period_end_date=datetime(2024, 12, 31),
            period_type="annual",
            fiscal_year=2024,
        )
        income = IncomeStatement(
            period=period,
            total_revenue=Decimal("1000000"),
            operating_income=Decimal("200000"),
            net_income=Decimal("150000"),
            earnings_per_share=Decimal("5.0"),
        )
        balance = BalanceSheet(
            period=period,
            total_equity=Decimal("3000000"),
        )
        cashflow = CashFlowStatement(
            period=period,
            operating_cash_flow=Decimal("250000"),
            capital_expenditures=Decimal("-50000"),
            free_cash_flow=Decimal("200000"),
            depreciation_amortization=Decimal("30000"),
        )

        ratios = provider._calculate_ratios(
            income=income,
            balance=balance,
            cashflow=cashflow,
            market_cap=None,
            current_price=Decimal("50.0"),
            shares_outstanding=30000000,
        )

        assert ratios is not None
        assert ratios.price_to_free_cash_flow is not None

    def test_calculate_ratios_with_market_data(self) -> None:
        """Test _calculate_ratios with market data."""
        provider = YFinanceFundamentalProvider()
        period = FinancialStatementPeriod(
            period_end_date=datetime(2024, 12, 31),
            period_type="annual",
            fiscal_year=2024,
        )
        income = IncomeStatement(
            period=period,
            total_revenue=Decimal("1000000"),
            net_income=Decimal("150000"),
            earnings_per_share=Decimal("5.0"),
        )
        balance = BalanceSheet(
            period=period,
            total_equity=Decimal("3000000"),
        )

        ratios = provider._calculate_ratios(
            income=income,
            balance=balance,
            cashflow=None,
            market_cap=Decimal("1500000000"),
            current_price=Decimal("50.0"),
            shares_outstanding=30000000,
            enterprise_value=Decimal("1600000000"),
        )

        assert ratios is not None
        assert ratios.price_to_earnings is not None
        assert ratios.price_to_book is not None
        assert ratios.price_to_sales is not None

    def test_calculate_ratios_with_growth_rates(self) -> None:
        """Test _calculate_ratios with growth rate calculations."""
        provider = YFinanceFundamentalProvider()
        period1 = FinancialStatementPeriod(
            period_end_date=datetime(2024, 12, 31),
            period_type="annual",
            fiscal_year=2024,
        )
        period2 = FinancialStatementPeriod(
            period_end_date=datetime(2023, 12, 31),
            period_type="annual",
            fiscal_year=2023,
        )

        income1 = IncomeStatement(
            period=period1,
            total_revenue=Decimal("1100000"),
            net_income=Decimal("165000"),
        )
        income2 = IncomeStatement(
            period=period2,
            total_revenue=Decimal("1000000"),
            net_income=Decimal("150000"),
        )

        cashflow1 = CashFlowStatement(
            period=period1,
            free_cash_flow=Decimal("220000"),
        )
        cashflow2 = CashFlowStatement(
            period=period2,
            free_cash_flow=Decimal("200000"),
        )

        ratios = provider._calculate_ratios(
            income=income1,
            balance=None,
            cashflow=cashflow1,
            market_cap=None,
            current_price=None,
            shares_outstanding=None,
            income_statements=[income1, income2],
            cash_flow_statements=[cashflow1, cashflow2],
        )

        assert ratios is not None
        assert ratios.revenue_growth is not None
        assert ratios.earnings_growth is not None
        assert ratios.free_cash_flow_growth is not None

    def test_calculate_ratios_with_none_inputs(self) -> None:
        """Test _calculate_ratios with None inputs."""
        provider = YFinanceFundamentalProvider()
        ratios = provider._calculate_ratios(
            income=None,
            balance=None,
            cashflow=None,
            market_cap=None,
            current_price=None,
            shares_outstanding=None,
        )

        assert ratios is not None
        assert isinstance(ratios, FinancialRatios)

    @pytest.mark.asyncio
    async def test_get_detailed_fundamentals_success(self) -> None:
        """Test get_detailed_fundamentals successfully."""
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "longName": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "marketCap": 3000000000000,
            "currentPrice": 150.0,
            "sharesOutstanding": 16000000000,
            "enterpriseValue": 3100000000000,
            "currency": "USD",
        }

        # Mock DataFrames
        mock_income_df = MagicMock()
        mock_income_df.empty = False
        mock_income_df.columns = [datetime(2024, 12, 31)]

        mock_balance_df = MagicMock()
        mock_balance_df.empty = False
        mock_balance_df.columns = [datetime(2024, 12, 31)]

        mock_cashflow_df = MagicMock()
        mock_cashflow_df.empty = False
        mock_cashflow_df.columns = [datetime(2024, 12, 31)]

        def income_getitem_side_effect(col):
            mock_series = MagicMock()
            mock_series.index = ["Total Revenue", "Net Income"]
            mock_series.loc = MagicMock(return_value=Decimal("1000000"))
            return mock_series

        mock_income_df.__getitem__ = MagicMock(side_effect=income_getitem_side_effect)

        def balance_getitem_side_effect(col):
            mock_series = MagicMock()
            mock_series.index = ["Total Assets", "Total Equity"]
            mock_series.loc = MagicMock(return_value=Decimal("5000000"))
            return mock_series

        mock_balance_df.__getitem__ = MagicMock(side_effect=balance_getitem_side_effect)

        def cashflow_getitem_side_effect(col):
            mock_series = MagicMock()
            mock_series.index = ["Operating Cash Flow", "Net Income"]
            mock_series.loc = MagicMock(return_value=Decimal("250000"))
            return mock_series

        mock_cashflow_df.__getitem__ = MagicMock(side_effect=cashflow_getitem_side_effect)

        mock_ticker.financials = mock_income_df
        mock_ticker.balance_sheet = mock_balance_df
        mock_ticker.cashflow = mock_cashflow_df

        with (
            patch("copinance_os.data.providers.yfinance.YFINANCE_AVAILABLE", True),
            patch(
                "asyncio.to_thread",
                new=AsyncMock(
                    side_effect=[
                        mock_ticker,
                        mock_ticker.info,
                        mock_income_df,
                        mock_balance_df,
                        mock_cashflow_df,
                    ]
                ),
            ),
        ):
            provider = YFinanceFundamentalProvider()
            result = await provider.get_detailed_fundamentals(
                "AAPL", periods=1, period_type="annual"
            )

            assert isinstance(result, StockFundamentals)
            assert result.symbol == "AAPL"
            assert result.company_name == "Apple Inc."

    @pytest.mark.asyncio
    async def test_get_detailed_fundamentals_uses_cache(self) -> None:
        """Test get_detailed_fundamentals uses cached data."""
        with patch("copinance_os.data.providers.yfinance.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2024, 1, 1, tzinfo=UTC)
            provider = YFinanceFundamentalProvider(cache_ttl_seconds=3600)
            cached_fundamentals = StockFundamentals(
                symbol="AAPL",
                company_name="Apple Inc.",
                income_statements=[],
                balance_sheets=[],
                cash_flow_statements=[],
                ratios=FinancialRatios(),
                provider="yfinance",
                data_as_of=datetime(2024, 1, 1, tzinfo=UTC),
            )
            provider._cache_fundamentals("AAPL", 5, "annual", cached_fundamentals)

            result = await provider.get_detailed_fundamentals(
                "AAPL", periods=5, period_type="annual"
            )

            assert result is cached_fundamentals

    @pytest.mark.asyncio
    async def test_get_detailed_fundamentals_empty_statements(self) -> None:
        """Test get_detailed_fundamentals when all statements are empty."""
        mock_ticker = MagicMock()
        mock_ticker.info = {}

        mock_income_df = MagicMock()
        mock_income_df.empty = True
        mock_balance_df = MagicMock()
        mock_balance_df.empty = True
        mock_cashflow_df = MagicMock()
        mock_cashflow_df.empty = True

        with (
            patch("copinance_os.data.providers.yfinance.YFINANCE_AVAILABLE", True),
            patch(
                "asyncio.to_thread",
                new=AsyncMock(
                    side_effect=[
                        mock_ticker,
                        mock_ticker.info,
                        mock_income_df,
                        mock_balance_df,
                        mock_cashflow_df,
                    ]
                ),
            ),
        ):
            provider = YFinanceFundamentalProvider()
            with pytest.raises(ValueError, match="No financial data found"):
                await provider.get_detailed_fundamentals("INVALID", periods=1, period_type="annual")

    @pytest.mark.asyncio
    async def test_get_detailed_fundamentals_yfinance_not_available(self) -> None:
        """Test get_detailed_fundamentals when yfinance not available."""
        with patch("copinance_os.data.providers.yfinance.YFINANCE_AVAILABLE", False):
            provider = YFinanceFundamentalProvider()
            with pytest.raises(ValueError, match="yfinance is not installed"):
                await provider.get_detailed_fundamentals("AAPL", periods=1, period_type="annual")
