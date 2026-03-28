"""Unit tests for market CLI commands."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copinance_os.domain.models.market import MarketDataPoint
from copinance_os.domain.models.stock import Stock
from copinance_os.interfaces.cli.market import (
    get_market_fundamentals,
    get_market_history,
    get_market_quote,
    search_instruments,
)
from copinance_os.research.workflows.fundamentals import (
    GetStockFundamentalsRequest,
)
from copinance_os.research.workflows.market import (
    GetHistoricalDataRequest,
    GetQuoteRequest,
    InstrumentSearchMode,
    SearchInstrumentsRequest,
    SearchInstrumentsResponse,
)


@pytest.mark.unit
class TestMarketCLI:
    """Test market-related CLI commands."""

    @patch("copinance_os.interfaces.cli.market.container.search_instruments_use_case")
    @patch("copinance_os.interfaces.cli.market.console")
    def test_search_instruments_with_results(
        self, mock_console: MagicMock, mock_use_case_provider: MagicMock
    ) -> None:
        mock_response = SearchInstrumentsResponse(
            instruments=[Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ")]
        )
        mock_use_case = AsyncMock()
        mock_use_case.execute = AsyncMock(return_value=mock_response)
        mock_use_case_provider.return_value = mock_use_case

        search_instruments(query="Apple", limit=10, search_mode=InstrumentSearchMode.AUTO)

        call_args = mock_use_case.execute.call_args[0][0]
        assert isinstance(call_args, SearchInstrumentsRequest)
        assert call_args.query == "Apple"
        assert call_args.limit == 10
        assert call_args.search_mode == InstrumentSearchMode.AUTO
        assert mock_console.print.called

    @patch("copinance_os.interfaces.cli.market.container.search_instruments_use_case")
    @patch("copinance_os.interfaces.cli.market.console")
    def test_search_instruments_no_results(
        self, mock_console: MagicMock, mock_use_case_provider: MagicMock
    ) -> None:
        mock_use_case = AsyncMock()
        mock_use_case.execute = AsyncMock(return_value=SearchInstrumentsResponse(instruments=[]))
        mock_use_case_provider.return_value = mock_use_case

        search_instruments(query="INVALID", limit=10, search_mode=InstrumentSearchMode.AUTO)

        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("No instruments found" in str(call) for call in print_calls)

    @patch("copinance_os.interfaces.cli.market.container.cache_manager")
    @patch("copinance_os.interfaces.cli.market.container.get_quote_use_case")
    @patch("copinance_os.interfaces.cli.market.console")
    def test_get_market_quote(
        self,
        mock_console: MagicMock,
        mock_use_case_provider: MagicMock,
        mock_cache_manager: MagicMock,
    ) -> None:
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        mock_cache_manager.return_value = cache

        mock_uc = AsyncMock()
        mock_uc.execute = AsyncMock(
            return_value=MagicMock(
                quote={
                    "symbol": "AAPL",
                    "current_price": Decimal("150.25"),
                    "previous_close": Decimal("149.10"),
                    "open": Decimal("150.00"),
                    "high": Decimal("151.00"),
                    "low": Decimal("148.90"),
                    "volume": 1000000,
                    "market_cap": 2000000000,
                    "currency": "USD",
                    "exchange": "NASDAQ",
                    "timestamp": "2026-03-14T09:30:00+00:00",
                },
                symbol="AAPL",
            )
        )
        mock_use_case_provider.return_value = mock_uc

        get_market_quote(symbol="aapl")

        mock_uc.execute.assert_called_once()
        call_args = mock_uc.execute.call_args[0][0]
        assert isinstance(call_args, GetQuoteRequest)
        assert call_args.symbol == "AAPL"
        assert mock_console.print.called

    @patch("copinance_os.interfaces.cli.market.container.cache_manager")
    @patch("copinance_os.interfaces.cli.market.container.get_historical_data_use_case")
    @patch("copinance_os.interfaces.cli.market.console")
    def test_get_market_history(
        self,
        mock_console: MagicMock,
        mock_use_case_provider: MagicMock,
        mock_cache_manager: MagicMock,
    ) -> None:
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        mock_cache_manager.return_value = cache

        mock_uc = AsyncMock()
        mock_uc.execute = AsyncMock(
            return_value=MagicMock(
                data=[
                    MarketDataPoint(
                        symbol="AAPL",
                        timestamp=datetime(2026, 3, 10, tzinfo=UTC),
                        open_price=Decimal("150.00"),
                        close_price=Decimal("151.00"),
                        high_price=Decimal("152.00"),
                        low_price=Decimal("149.00"),
                        volume=1000000,
                    )
                ],
                symbol="AAPL",
            )
        )
        mock_use_case_provider.return_value = mock_uc

        get_market_history(
            symbol="aapl",
            start_date="2026-03-01",
            end_date="2026-03-14",
            interval="1d",
            limit=10,
        )

        mock_uc.execute.assert_called_once()
        call_args = mock_uc.execute.call_args[0][0]
        assert isinstance(call_args, GetHistoricalDataRequest)
        assert call_args.symbol == "AAPL"
        assert call_args.interval == "1d"
        assert mock_console.print.called

    @patch("copinance_os.interfaces.cli.market.handle_cli_error")
    @patch("copinance_os.interfaces.cli.market.console")
    def test_get_market_history_rejects_invalid_interval(
        self, mock_console: MagicMock, mock_handle_error: MagicMock
    ) -> None:
        get_market_history(
            symbol="AAPL",
            start_date="2026-03-01",
            end_date="2026-03-14",
            interval="2d",
            limit=10,
        )

        mock_handle_error.assert_called_once()
        mock_console.print.assert_not_called()

    @patch("copinance_os.interfaces.cli.market.container.cache_manager")
    @patch("copinance_os.interfaces.cli.market.container.get_stock_fundamentals_use_case")
    @patch("copinance_os.interfaces.cli.market.console")
    def test_get_market_fundamentals(
        self,
        mock_console: MagicMock,
        mock_use_case_provider: MagicMock,
        mock_cache_manager: MagicMock,
    ) -> None:
        cache = AsyncMock()
        cache.get = AsyncMock(return_value=None)
        mock_cache_manager.return_value = cache

        fundamentals_dict = {
            "symbol": "AAPL",
            "company_name": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "market_cap": "2800000000000",
            "current_price": "175.50",
            "provider": "yfinance",
            "data_as_of": "2026-03-14T12:00:00+00:00",
            "income_statements": [],
            "balance_sheets": [],
            "cash_flow_statements": [],
            "ratios": {"price_to_earnings": "28.5", "return_on_equity": "147.2"},
        }
        mock_fundamentals = MagicMock()
        mock_fundamentals.model_dump = MagicMock(return_value=fundamentals_dict)

        mock_uc = AsyncMock()
        mock_uc.execute = AsyncMock(return_value=MagicMock(fundamentals=mock_fundamentals))
        mock_use_case_provider.return_value = mock_uc

        get_market_fundamentals(symbol="aapl", periods=5, period_type="annual")

        mock_uc.execute.assert_called_once()
        call_args = mock_uc.execute.call_args[0][0]
        assert isinstance(call_args, GetStockFundamentalsRequest)
        assert call_args.symbol == "AAPL"
        assert call_args.periods == 5
        assert call_args.period_type == "annual"
        assert mock_console.print.called
