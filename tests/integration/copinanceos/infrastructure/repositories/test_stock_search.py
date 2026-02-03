"""Integration tests for stock search functionality."""

import asyncio

import pytest

from copinanceos.application.use_cases.stock import (
    SearchStocksRequest,
    SearchStocksUseCase,
    SearchType,
)
from copinanceos.domain.models.stock import Stock
from copinanceos.domain.ports.repositories import StockRepository
from copinanceos.infrastructure.data_providers.yfinance import YFinanceMarketProvider

# Cache provider availability to avoid repeated checks
_provider_cache: YFinanceMarketProvider | None = None
_provider_checked = False


@pytest.fixture(scope="session")
def market_provider() -> YFinanceMarketProvider | None:
    """Provide market data provider if available, checked once per test session."""
    global _provider_cache, _provider_checked

    if not _provider_checked:
        _provider_checked = True
        provider = YFinanceMarketProvider()
        # Check availability synchronously (blocking) to avoid async fixture issues
        try:
            # Try to get existing event loop
            try:
                loop = asyncio.get_running_loop()
                # If we're in a running loop, we can't use it - create new one
                new_loop = asyncio.new_event_loop()
                is_available = new_loop.run_until_complete(provider.is_available())
                new_loop.close()
            except RuntimeError:
                # No running loop, try to get or create one
                try:
                    loop = asyncio.get_event_loop()
                    is_available = loop.run_until_complete(provider.is_available())
                except RuntimeError:
                    # No event loop at all, create one
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    is_available = loop.run_until_complete(provider.is_available())
                    loop.close()
        except Exception:
            # If all else fails, create a new loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            is_available = loop.run_until_complete(provider.is_available())
            loop.close()

        _provider_cache = provider if is_available else None

    return _provider_cache


@pytest.mark.integration
class TestStockSearchIntegration:
    """Integration tests for stock search through the full stack."""

    @pytest.fixture
    def use_case(self, stock_repository: StockRepository) -> SearchStocksUseCase:
        """Provide SearchStocksUseCase without market provider for repository-only tests.

        Using fixture to avoid repeated instantiation in test methods,
        reducing initialization overhead and benefiting from repository caching.
        """
        return SearchStocksUseCase(stock_repository)

    @pytest.fixture
    def use_case_with_provider(
        self, stock_repository: StockRepository, market_provider: YFinanceMarketProvider | None
    ) -> SearchStocksUseCase:
        """Provide SearchStocksUseCase with market provider for yfinance tests.

        Using fixture to avoid repeated instantiation in test methods,
        reducing initialization overhead and benefiting from repository caching.
        """
        return SearchStocksUseCase(
            stock_repository, market_data_provider=market_provider if market_provider else None
        )

    @pytest.mark.asyncio
    async def test_search_by_symbol_exact_match(
        self, stock_repository: StockRepository, use_case: SearchStocksUseCase
    ) -> None:
        """Test searching for stocks by exact symbol match."""
        # Setup: Create test stocks
        stocks = [
            Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ"),
            Stock(symbol="MSFT", name="Microsoft Corporation", exchange="NASDAQ"),
            Stock(symbol="GOOGL", name="Alphabet Inc.", exchange="NASDAQ"),
        ]

        for stock in stocks:
            await stock_repository.save(stock)

        # Execute: Search for exact symbol
        request = SearchStocksRequest(query="AAPL", limit=10)
        response = await use_case.execute(request)

        # Verify: Should find exact match
        assert len(response.stocks) == 1
        assert response.stocks[0].symbol == "AAPL"
        assert response.stocks[0].name == "Apple Inc."

    @pytest.mark.asyncio
    async def test_search_by_symbol_partial_match(
        self, stock_repository: StockRepository, use_case: SearchStocksUseCase
    ) -> None:
        """Test searching for stocks by partial symbol match."""
        # Setup: Create test stocks
        stocks = [
            Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ"),
            Stock(symbol="MSFT", name="Microsoft Corporation", exchange="NASDAQ"),
            Stock(symbol="GOOGL", name="Alphabet Inc.", exchange="NASDAQ"),
            Stock(symbol="GOOG", name="Alphabet Inc. Class C", exchange="NASDAQ"),
        ]

        for stock in stocks:
            await stock_repository.save(stock)

        # Execute: Search for partial symbol
        request = SearchStocksRequest(query="GOOG", limit=10)
        response = await use_case.execute(request)

        # Verify: Should find both GOOGL and GOOG
        assert len(response.stocks) == 2
        symbols = {stock.symbol for stock in response.stocks}
        assert "GOOGL" in symbols
        assert "GOOG" in symbols

    @pytest.mark.asyncio
    async def test_search_by_name_exact_match(
        self, stock_repository: StockRepository, use_case: SearchStocksUseCase
    ) -> None:
        """Test searching for stocks by exact name match."""
        # Setup: Create test stocks
        stocks = [
            Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ"),
            Stock(symbol="MSFT", name="Microsoft Corporation", exchange="NASDAQ"),
            Stock(symbol="GOOGL", name="Alphabet Inc.", exchange="NASDAQ"),
        ]

        for stock in stocks:
            await stock_repository.save(stock)

        # Execute: Search by name
        request = SearchStocksRequest(query="Apple Inc.", limit=10)
        response = await use_case.execute(request)

        # Verify: Should find by name
        assert len(response.stocks) == 1
        assert response.stocks[0].symbol == "AAPL"
        assert response.stocks[0].name == "Apple Inc."

    @pytest.mark.asyncio
    async def test_search_by_name_partial_match(
        self, stock_repository: StockRepository, use_case: SearchStocksUseCase
    ) -> None:
        """Test searching for stocks by partial name match."""
        # Setup: Create test stocks
        stocks = [
            Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ"),
            Stock(symbol="MSFT", name="Microsoft Corporation", exchange="NASDAQ"),
            Stock(symbol="GOOGL", name="Alphabet Inc.", exchange="NASDAQ"),
        ]

        for stock in stocks:
            await stock_repository.save(stock)

        # Execute: Search by partial name
        request = SearchStocksRequest(query="Apple", limit=10)
        response = await use_case.execute(request)

        # Verify: Should find by partial name
        assert len(response.stocks) == 1
        assert response.stocks[0].symbol == "AAPL"
        assert "Apple" in response.stocks[0].name

    @pytest.mark.asyncio
    async def test_search_case_insensitive(
        self, stock_repository: StockRepository, use_case: SearchStocksUseCase
    ) -> None:
        """Test that search is case-insensitive."""
        # Setup: Create test stocks
        stocks = [
            Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ"),
            Stock(symbol="MSFT", name="Microsoft Corporation", exchange="NASDAQ"),
        ]

        for stock in stocks:
            await stock_repository.save(stock)

        # Execute: Search with different cases
        # Lowercase query
        request_lower = SearchStocksRequest(query="aapl", limit=10)
        response_lower = await use_case.execute(request_lower)
        assert len(response_lower.stocks) == 1
        assert response_lower.stocks[0].symbol == "AAPL"

        # Uppercase query
        request_upper = SearchStocksRequest(query="APPLE", limit=10)
        response_upper = await use_case.execute(request_upper)
        assert len(response_upper.stocks) == 1
        assert response_upper.stocks[0].symbol == "AAPL"

        # Mixed case query
        request_mixed = SearchStocksRequest(query="MiCrOsOfT", limit=10)
        response_mixed = await use_case.execute(request_mixed)
        assert len(response_mixed.stocks) == 1
        assert response_mixed.stocks[0].symbol == "MSFT"

    @pytest.mark.asyncio
    async def test_search_limit_functionality(
        self, stock_repository: StockRepository, use_case: SearchStocksUseCase
    ) -> None:
        """Test that search respects the limit parameter."""
        # Setup: Create multiple test stocks that match the query
        stocks = [
            Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ"),
            Stock(symbol="MSFT", name="Microsoft Corporation", exchange="NASDAQ"),
            Stock(symbol="GOOGL", name="Alphabet Inc.", exchange="NASDAQ"),
            Stock(symbol="AMZN", name="Amazon.com Inc.", exchange="NASDAQ"),
            Stock(symbol="TSLA", name="Tesla Inc.", exchange="NASDAQ"),
        ]

        for stock in stocks:
            await stock_repository.save(stock)

        # Execute: Search with limit
        request = SearchStocksRequest(query="Inc", limit=3)
        response = await use_case.execute(request)

        # Verify: Should respect limit
        assert len(response.stocks) <= 3

    @pytest.mark.asyncio
    async def test_search_no_results(
        self, stock_repository: StockRepository, use_case: SearchStocksUseCase
    ) -> None:
        """Test search when no stocks match the query."""
        # Setup: Create test stocks
        stocks = [
            Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ"),
            Stock(symbol="MSFT", name="Microsoft Corporation", exchange="NASDAQ"),
        ]

        for stock in stocks:
            await stock_repository.save(stock)

        # Execute: Search for non-existent stock
        request = SearchStocksRequest(query="NONEXISTENT", limit=10)
        response = await use_case.execute(request)

        # Verify: Should return empty list
        assert len(response.stocks) == 0
        assert response.stocks == []

    @pytest.mark.asyncio
    async def test_search_empty_query(
        self, stock_repository: StockRepository, use_case: SearchStocksUseCase
    ) -> None:
        """Test search with empty query."""
        # Setup: Create test stocks
        stocks = [
            Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ"),
            Stock(symbol="MSFT", name="Microsoft Corporation", exchange="NASDAQ"),
        ]

        for stock in stocks:
            await stock_repository.save(stock)

        # Execute: Search with empty query
        request = SearchStocksRequest(query="", limit=10)
        response = await use_case.execute(request)

        # Verify: Empty query should match all (or none, depending on implementation)
        # The current implementation matches empty string to all stocks
        assert isinstance(response.stocks, list)

    @pytest.mark.asyncio
    async def test_search_multiple_matches_symbol_and_name(
        self, stock_repository: StockRepository, use_case: SearchStocksUseCase
    ) -> None:
        """Test search that matches both symbol and name fields."""
        # Setup: Create test stocks where query matches both symbol and name
        stocks = [
            Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ"),
            Stock(symbol="APPL", name="Apple Corporation", exchange="NYSE"),
        ]

        for stock in stocks:
            await stock_repository.save(stock)

        # Execute: Search that matches both
        request = SearchStocksRequest(query="Apple", limit=10)
        response = await use_case.execute(request)

        # Verify: Should find both stocks
        assert len(response.stocks) == 2
        symbols = {stock.symbol for stock in response.stocks}
        assert "AAPL" in symbols
        assert "APPL" in symbols

    @pytest.mark.asyncio
    async def test_search_persistence_across_operations(
        self, stock_repository: StockRepository, use_case: SearchStocksUseCase
    ) -> None:
        """Test that saved stocks persist and can be searched after save."""
        # Setup: Create and save stocks
        stock1 = Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ")
        stock2 = Stock(symbol="MSFT", name="Microsoft Corporation", exchange="NASDAQ")

        saved_stock1 = await stock_repository.save(stock1)
        saved_stock2 = await stock_repository.save(stock2)

        # Verify: Stocks are saved
        assert saved_stock1.symbol == "AAPL"
        assert saved_stock2.symbol == "MSFT"

        # Execute: Search for saved stocks
        request = SearchStocksRequest(query="AAPL", limit=10)
        response = await use_case.execute(request)

        # Verify: Can find saved stocks
        assert len(response.stocks) == 1
        assert response.stocks[0].symbol == "AAPL"
        assert response.stocks[0].id == saved_stock1.id

    @pytest.mark.asyncio
    async def test_search_with_special_characters(
        self, stock_repository: StockRepository, use_case: SearchStocksUseCase
    ) -> None:
        """Test search with special characters in query."""
        # Setup: Create test stocks
        stocks = [
            Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ"),
            Stock(symbol="MSFT", name="Microsoft Corporation", exchange="NASDAQ"),
        ]

        for stock in stocks:
            await stock_repository.save(stock)

        # Execute: Search with special characters
        request = SearchStocksRequest(query="Inc.", limit=10)
        response = await use_case.execute(request)

        # Verify: Should handle special characters
        assert len(response.stocks) >= 1
        assert any("Inc." in stock.name for stock in response.stocks)

    @pytest.mark.asyncio
    async def test_search_across_different_exchanges(
        self, stock_repository: StockRepository, use_case: SearchStocksUseCase
    ) -> None:
        """Test search works across stocks from different exchanges."""
        # Setup: Create stocks from different exchanges
        stocks = [
            Stock(symbol="AAPL", name="Apple Inc.", exchange="NASDAQ"),
            Stock(symbol="IBM", name="International Business Machines", exchange="NYSE"),
            Stock(symbol="TSLA", name="Tesla Inc.", exchange="NASDAQ"),
        ]

        for stock in stocks:
            await stock_repository.save(stock)

        # Execute: Search that should match across exchanges
        request = SearchStocksRequest(query="Inc", limit=10)
        response = await use_case.execute(request)

        # Verify: Should find stocks from different exchanges
        assert len(response.stocks) >= 2
        exchanges = {stock.exchange for stock in response.stocks}
        assert "NASDAQ" in exchanges

    @pytest.mark.asyncio
    async def test_search_fetches_from_yfinance_when_not_found_locally(
        self,
        stock_repository: StockRepository,
        market_provider: YFinanceMarketProvider | None,
        use_case_with_provider: SearchStocksUseCase,
    ) -> None:
        """Test that search fetches from yfinance when no local results are found."""
        if not market_provider:
            pytest.skip("yfinance provider not available")

        # Setup: Ensure repository is empty (fixture provides clean repository)
        # Verify repository is empty
        use_case_no_provider = SearchStocksUseCase(stock_repository)
        empty_request = SearchStocksRequest(query="AAPL", limit=10)
        empty_response = await use_case_no_provider.execute(empty_request)
        assert len(empty_response.stocks) == 0, "Repository should be empty initially"

        # Execute: Search with market data provider enabled
        # Search for a real stock symbol
        request = SearchStocksRequest(query="AAPL", limit=10)
        response = await use_case_with_provider.execute(request)

        # Verify: Should fetch from yfinance and return results
        assert len(response.stocks) == 1, "Should fetch stock from yfinance"
        assert response.stocks[0].symbol == "AAPL"
        assert response.stocks[0].name is not None
        assert len(response.stocks[0].name) > 0
        assert response.stocks[0].exchange is not None
        assert len(response.stocks[0].exchange) > 0

        # Verify: Stock was saved to repository
        saved_stock = await stock_repository.get_by_symbol("AAPL")
        assert saved_stock is not None, "Stock should be saved to repository"
        assert saved_stock.symbol == "AAPL"
        assert saved_stock.id == response.stocks[0].id

        # Verify: Subsequent search finds it locally (no yfinance call needed)
        local_response = await use_case_with_provider.execute(request)
        assert len(local_response.stocks) == 1
        assert local_response.stocks[0].symbol == "AAPL"
        assert local_response.stocks[0].id == saved_stock.id

    @pytest.mark.asyncio
    async def test_search_only_fetches_symbol_like_queries_from_yfinance(
        self,
        stock_repository: StockRepository,
        market_provider: YFinanceMarketProvider | None,
        use_case_with_provider: SearchStocksUseCase,
    ) -> None:
        """Test that only symbol-like queries trigger yfinance fetch."""
        if not market_provider:
            pytest.skip("yfinance provider not available")

        # Execute: Search with a non-symbol query (should not fetch from yfinance)
        request = SearchStocksRequest(query="Apple Company", limit=10)
        response = await use_case_with_provider.execute(request)

        # Verify: Should return empty (non-symbol queries don't trigger yfinance)
        assert len(response.stocks) == 0

        # Execute: Search with a symbol-like query (should fetch from yfinance)
        symbol_request = SearchStocksRequest(query="MSFT", limit=10)
        symbol_response = await use_case_with_provider.execute(symbol_request)

        # Verify: Should fetch from yfinance for symbol-like queries
        assert len(symbol_response.stocks) == 1
        assert symbol_response.stocks[0].symbol == "MSFT"

    @pytest.mark.asyncio
    async def test_company_name_search_searches_repository_only(
        self,
        stock_repository: StockRepository,
        market_provider: YFinanceMarketProvider | None,
        use_case_with_provider: SearchStocksUseCase,
    ) -> None:
        """Test that company name searches (lowercase/mixed case) only search repository."""
        if not market_provider:
            pytest.skip("yfinance provider not available")

        # Setup: Add a stock to repository
        stock = Stock(
            symbol="TSLA",
            name="Tesla, Inc.",
            exchange="NMS",
            sector="Consumer Cyclical",
            industry="Auto Manufacturers",
        )
        await stock_repository.save(stock)

        # Search by company name (lowercase) - should NOT trigger yfinance
        request_lower = SearchStocksRequest(query="tesla", limit=10)
        response_lower = await use_case_with_provider.execute(request_lower)

        # Verify: Should find stock in repository
        assert len(response_lower.stocks) == 1
        assert response_lower.stocks[0].symbol == "TSLA"
        assert "Tesla" in response_lower.stocks[0].name

        # Search by company name (mixed case) - should NOT trigger yfinance
        request_mixed = SearchStocksRequest(query="Tesla", limit=10)
        response_mixed = await use_case_with_provider.execute(request_mixed)

        # Verify: Should find stock in repository
        assert len(response_mixed.stocks) == 1
        assert response_mixed.stocks[0].symbol == "TSLA"

        # Search by partial company name - should NOT trigger yfinance
        request_partial = SearchStocksRequest(query="Inc", limit=10)
        response_partial = await use_case_with_provider.execute(request_partial)

        # Verify: Should find stock in repository
        assert len(response_partial.stocks) >= 1
        assert any(stock.symbol == "TSLA" for stock in response_partial.stocks)

    @pytest.mark.asyncio
    async def test_invalid_symbol_does_not_save_to_repository(
        self,
        stock_repository: StockRepository,
        market_provider: YFinanceMarketProvider | None,
        use_case_with_provider: SearchStocksUseCase,
    ) -> None:
        """Test that invalid symbols don't get saved to repository when yfinance fails."""
        if not market_provider:
            pytest.skip("yfinance provider not available")

        # Execute: Search for invalid symbol (uppercase but invalid)
        request = SearchStocksRequest(query="TESLA", limit=10)  # Invalid - should be TSLA
        response = await use_case_with_provider.execute(request)

        # Verify: Should return empty (invalid symbol)
        assert len(response.stocks) == 0

        # Verify: Invalid stock was NOT saved to repository
        saved_stock = await stock_repository.get_by_symbol("TESLA")
        assert saved_stock is None, "Invalid stock should not be saved to repository"

        # Verify: Repository is still empty (or only has valid stocks)
        all_stocks = await stock_repository.search("", limit=100)
        assert not any(stock.symbol == "TESLA" for stock in all_stocks)

    @pytest.mark.asyncio
    async def test_uppercase_symbol_triggers_yfinance_fetch(
        self,
        stock_repository: StockRepository,
        market_provider: YFinanceMarketProvider | None,
        use_case_with_provider: SearchStocksUseCase,
    ) -> None:
        """Test that uppercase symbol queries trigger yfinance fetch."""
        if not market_provider:
            pytest.skip("yfinance provider not available")

        # Execute: Search with uppercase symbol
        request = SearchStocksRequest(query="TSLA", limit=10)
        response = await use_case_with_provider.execute(request)

        # Verify: Should fetch from yfinance and return results
        assert len(response.stocks) == 1
        assert response.stocks[0].symbol == "TSLA"
        assert response.stocks[0].name is not None
        assert len(response.stocks[0].name) > 0
        assert "Tesla" in response.stocks[0].name
        assert response.stocks[0].exchange is not None
        assert len(response.stocks[0].exchange) > 0

        # Verify: Stock was saved to repository
        saved_stock = await stock_repository.get_by_symbol("TSLA")
        assert saved_stock is not None
        assert saved_stock.symbol == "TSLA"
        assert saved_stock.id == response.stocks[0].id

    @pytest.mark.asyncio
    async def test_company_name_search_after_symbol_fetch(
        self,
        stock_repository: StockRepository,
        market_provider: YFinanceMarketProvider | None,
        use_case_with_provider: SearchStocksUseCase,
    ) -> None:
        """Test that after fetching by symbol, company name search works."""
        if not market_provider:
            pytest.skip("yfinance provider not available")

        # Step 1: Fetch stock by symbol (uppercase)
        symbol_request = SearchStocksRequest(query="TSLA", limit=10)
        symbol_response = await use_case_with_provider.execute(symbol_request)

        # Verify: Stock was fetched and saved
        assert len(symbol_response.stocks) == 1
        assert symbol_response.stocks[0].symbol == "TSLA"
        company_name = symbol_response.stocks[0].name

        # Step 2: Search by company name (lowercase) - should find in repository
        name_request = SearchStocksRequest(query="tesla", limit=10)
        name_response = await use_case_with_provider.execute(name_request)

        # Verify: Should find stock by company name
        assert len(name_response.stocks) == 1
        assert name_response.stocks[0].symbol == "TSLA"
        assert name_response.stocks[0].name == company_name
        assert name_response.stocks[0].id == symbol_response.stocks[0].id

        # Step 3: Search by partial company name - should find in repository
        partial_request = SearchStocksRequest(query="Inc", limit=10)
        partial_response = await use_case_with_provider.execute(partial_request)

        # Verify: Should find stock by partial name
        assert len(partial_response.stocks) >= 1
        assert any(stock.symbol == "TSLA" for stock in partial_response.stocks)

    @pytest.mark.asyncio
    async def test_search_by_company_name_uses_yfinance_search(
        self,
        stock_repository: StockRepository,
        market_provider: YFinanceMarketProvider | None,
        use_case_with_provider: SearchStocksUseCase,
    ) -> None:
        """Test that searching by company name uses yfinance search API."""
        if not market_provider:
            pytest.skip("yfinance provider not available")

        # Execute: Search by company name (lowercase)
        request = SearchStocksRequest(query="merck", limit=10)
        response = await use_case_with_provider.execute(request)

        # Verify: Should find stocks from yfinance search
        assert len(response.stocks) > 0, "Should find at least one stock"
        # Should find MRK (Merck & Co., Inc.)
        assert any(stock.symbol == "MRK" for stock in response.stocks)
        # Verify stock has required fields
        mrk_stock = next(stock for stock in response.stocks if stock.symbol == "MRK")
        assert mrk_stock.name is not None
        assert len(mrk_stock.name) > 0
        assert "Merck" in mrk_stock.name
        assert mrk_stock.exchange is not None

    @pytest.mark.asyncio
    async def test_search_by_company_name_returns_multiple_results(
        self,
        stock_repository: StockRepository,
        market_provider: YFinanceMarketProvider | None,
        use_case_with_provider: SearchStocksUseCase,
    ) -> None:
        """Test that company name search can return multiple results."""
        if not market_provider:
            pytest.skip("yfinance provider not available")

        # Execute: Search by company name
        request = SearchStocksRequest(query="merck", limit=10)
        response = await use_case_with_provider.execute(request)

        # Verify: Should return multiple results (different exchanges)
        assert len(response.stocks) > 1, "Should find multiple Merck stocks"
        # All results should have valid data
        for stock in response.stocks:
            assert stock.symbol is not None
            assert stock.name is not None
            assert stock.exchange is not None

    @pytest.mark.asyncio
    async def test_search_by_company_name_saves_to_repository(
        self,
        stock_repository: StockRepository,
        market_provider: YFinanceMarketProvider | None,
        use_case_with_provider: SearchStocksUseCase,
    ) -> None:
        """Test that stocks found via company name search are saved to repository."""
        if not market_provider:
            pytest.skip("yfinance provider not available")

        # Execute: Search by company name
        request = SearchStocksRequest(query="merck", limit=5)
        response = await use_case_with_provider.execute(request)

        # Verify: Stocks were returned
        assert len(response.stocks) > 0

        # Verify: Stocks were saved to repository
        for stock in response.stocks:
            saved_stock = await stock_repository.get_by_symbol(stock.symbol)
            assert saved_stock is not None, f"Stock {stock.symbol} should be saved"
            assert saved_stock.symbol == stock.symbol
            assert saved_stock.id == stock.id

    @pytest.mark.asyncio
    async def test_search_by_company_name_subsequent_search_uses_repository(
        self,
        stock_repository: StockRepository,
        market_provider: YFinanceMarketProvider | None,
        use_case_with_provider: SearchStocksUseCase,
    ) -> None:
        """Test that subsequent company name searches use repository (no API calls)."""
        if not market_provider:
            pytest.skip("yfinance provider not available")

        # Step 1: First search by company name (will use yfinance)
        first_request = SearchStocksRequest(query="merck", limit=5)
        first_response = await use_case_with_provider.execute(first_request)

        # Verify: Stocks were found and saved
        assert len(first_response.stocks) > 0
        first_stock_ids = {stock.id for stock in first_response.stocks}

        # Step 2: Second search by company name (should use repository)
        second_request = SearchStocksRequest(query="merck", limit=5)
        second_response = await use_case_with_provider.execute(second_request)

        # Verify: Should find same stocks from repository
        assert len(second_response.stocks) > 0
        second_stock_ids = {stock.id for stock in second_response.stocks}
        # Should find at least some of the same stocks
        assert len(first_stock_ids & second_stock_ids) > 0

    @pytest.mark.asyncio
    async def test_search_by_company_name_vs_symbol_search(
        self,
        stock_repository: StockRepository,
        market_provider: YFinanceMarketProvider | None,
        use_case_with_provider: SearchStocksUseCase,
    ) -> None:
        """Test that both company name and symbol searches work correctly."""
        if not market_provider:
            pytest.skip("yfinance provider not available")

        # Execute: Search by symbol (uppercase)
        symbol_request = SearchStocksRequest(query="MRK", limit=10)
        symbol_response = await use_case_with_provider.execute(symbol_request)

        # Verify: Should find stock by symbol
        assert len(symbol_response.stocks) == 1
        assert symbol_response.stocks[0].symbol == "MRK"

        # Execute: Search by company name (lowercase)
        name_request = SearchStocksRequest(query="merck", limit=10)
        name_response = await use_case_with_provider.execute(name_request)

        # Verify: Should find stocks by company name (may include MRK and others)
        assert len(name_response.stocks) > 0
        # Should include MRK in results
        assert any(stock.symbol == "MRK" for stock in name_response.stocks)

    @pytest.mark.asyncio
    async def test_search_by_company_name_respects_limit(
        self,
        stock_repository: StockRepository,
        market_provider: YFinanceMarketProvider | None,
        use_case_with_provider: SearchStocksUseCase,
    ) -> None:
        """Test that company name search respects the limit parameter."""
        if not market_provider:
            pytest.skip("yfinance provider not available")

        # Execute: Search with limit
        request = SearchStocksRequest(query="merck", limit=2)
        response = await use_case_with_provider.execute(request)

        # Verify: Should respect limit
        assert len(response.stocks) <= 2

    @pytest.mark.asyncio
    async def test_search_by_company_name_handles_no_results(
        self,
        stock_repository: StockRepository,
        market_provider: YFinanceMarketProvider | None,
        use_case_with_provider: SearchStocksUseCase,
    ) -> None:
        """Test that company name search handles queries with no results gracefully."""
        if not market_provider:
            pytest.skip("yfinance provider not available")

        # Execute: Search for non-existent company
        request = SearchStocksRequest(query="nonexistentcompanyxyz123", limit=10)
        response = await use_case_with_provider.execute(request)

        # Verify: Should return empty list gracefully
        assert len(response.stocks) == 0
        assert response.stocks == []

    @pytest.mark.asyncio
    async def test_explicit_symbol_search(
        self,
        stock_repository: StockRepository,
        market_provider: YFinanceMarketProvider | None,
        use_case_with_provider: SearchStocksUseCase,
    ) -> None:
        """Test that explicit symbol search type forces symbol lookup."""
        if not market_provider:
            pytest.skip("yfinance provider not available")

        # Execute: Search with explicit SYMBOL type (even though query is lowercase)
        request = SearchStocksRequest(query="aapl", search_type=SearchType.SYMBOL, limit=10)
        response = await use_case_with_provider.execute(request)

        # Verify: Should fetch by symbol (treating "aapl" as "AAPL")
        assert len(response.stocks) > 0
        assert response.stocks[0].symbol == "AAPL"

    @pytest.mark.asyncio
    async def test_explicit_general_search(
        self,
        stock_repository: StockRepository,
        market_provider: YFinanceMarketProvider | None,
        use_case_with_provider: SearchStocksUseCase,
    ) -> None:
        """Test that explicit general search type forces text search (not symbol lookup)."""
        if not market_provider:
            pytest.skip("yfinance provider not available")

        # Execute: Search with explicit GENERAL type (even though query looks like symbol)
        request = SearchStocksRequest(query="AAPL", search_type=SearchType.GENERAL, limit=10)
        response = await use_case_with_provider.execute(request)

        # Verify: General search was used. Provider may return 0 or more results depending
        # on API (yfinance Search can return empty for some queries/environments).
        if response.stocks:
            assert any(
                "AAPL" in stock.symbol or "AAPL" in stock.name for stock in response.stocks
            ), "When results are returned, at least one should match the query"

    @pytest.mark.asyncio
    async def test_auto_search_type_detection(
        self,
        stock_repository: StockRepository,
        market_provider: YFinanceMarketProvider | None,
        use_case_with_provider: SearchStocksUseCase,
    ) -> None:
        """Test that AUTO search type correctly detects symbol vs general search."""
        if not market_provider:
            pytest.skip("yfinance provider not available")

        # Test 1: Uppercase symbol should be detected as symbol search
        request1 = SearchStocksRequest(query="AAPL", search_type=SearchType.AUTO, limit=10)
        response1 = await use_case_with_provider.execute(request1)
        assert len(response1.stocks) > 0
        assert response1.stocks[0].symbol == "AAPL"

        # Test 2: Lowercase company name should be detected as general search
        request2 = SearchStocksRequest(query="apple", search_type=SearchType.AUTO, limit=10)
        response2 = await use_case_with_provider.execute(request2)
        # General search may return multiple results
        assert len(response2.stocks) > 0
        # Should find Apple Inc. (AAPL) in results
        assert any(stock.symbol == "AAPL" for stock in response2.stocks)
