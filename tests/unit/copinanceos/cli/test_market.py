"""Unit tests for market CLI commands."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copinanceos.application.use_cases.market import (
    InstrumentSearchMode,
    SearchInstrumentsRequest,
    SearchInstrumentsResponse,
)
from copinanceos.cli.market import get_market_history, get_market_quote, search_instruments
from copinanceos.domain.models.market import MarketDataPoint
from copinanceos.domain.models.stock import Stock


@pytest.mark.unit
class TestMarketCLI:
    """Test market-related CLI commands."""

    @patch("copinanceos.cli.market.container.search_instruments_use_case")
    @patch("copinanceos.cli.market.console")
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

    @patch("copinanceos.cli.market.container.search_instruments_use_case")
    @patch("copinanceos.cli.market.console")
    def test_search_instruments_no_results(
        self, mock_console: MagicMock, mock_use_case_provider: MagicMock
    ) -> None:
        mock_use_case = AsyncMock()
        mock_use_case.execute = AsyncMock(return_value=SearchInstrumentsResponse(instruments=[]))
        mock_use_case_provider.return_value = mock_use_case

        search_instruments(query="INVALID", limit=10, search_mode=InstrumentSearchMode.AUTO)

        print_calls = [str(call) for call in mock_console.print.call_args_list]
        assert any("No instruments found" in str(call) for call in print_calls)

    @patch("copinanceos.cli.market.container.market_data_provider")
    @patch("copinanceos.cli.market.console")
    def test_get_market_quote(self, mock_console: MagicMock, mock_provider: MagicMock) -> None:
        provider = AsyncMock()
        provider.get_quote = AsyncMock(
            return_value={
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
            }
        )
        mock_provider.return_value = provider

        get_market_quote(symbol="aapl")

        provider.get_quote.assert_called_once_with("AAPL")
        assert mock_console.print.called

    @patch("copinanceos.cli.market.container.market_data_provider")
    @patch("copinanceos.cli.market.console")
    def test_get_market_history(self, mock_console: MagicMock, mock_provider: MagicMock) -> None:
        provider = AsyncMock()
        provider.get_historical_data = AsyncMock(
            return_value=[
                MarketDataPoint(
                    symbol="AAPL",
                    timestamp=datetime(2026, 3, 10, tzinfo=UTC),
                    open_price=Decimal("150.00"),
                    close_price=Decimal("151.00"),
                    high_price=Decimal("152.00"),
                    low_price=Decimal("149.00"),
                    volume=1000000,
                )
            ]
        )
        mock_provider.return_value = provider

        get_market_history(
            symbol="aapl",
            start_date="2026-03-01",
            end_date="2026-03-14",
            interval="1d",
            limit=10,
        )

        provider.get_historical_data.assert_called_once()
        call_kwargs = provider.get_historical_data.call_args.kwargs
        assert call_kwargs["symbol"] == "AAPL"
        assert call_kwargs["interval"] == "1d"
        assert mock_console.print.called

    @patch("copinanceos.cli.market.handle_cli_error")
    @patch("copinanceos.cli.market.console")
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
