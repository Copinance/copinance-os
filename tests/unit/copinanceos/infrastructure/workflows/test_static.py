"""Unit tests for stock workflow executor."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from copinanceos.application.use_cases.fundamentals import (
    ResearchStockFundamentalsResponse,
    ResearchStockFundamentalsUseCase,
)
from copinanceos.application.use_cases.stock import GetStockResponse, GetStockUseCase
from copinanceos.domain.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    FinancialRatios,
    FinancialStatementPeriod,
    IncomeStatement,
    StockFundamentals,
)
from copinanceos.domain.models.research import Research, ResearchTimeframe
from copinanceos.domain.models.stock import Stock
from copinanceos.domain.ports.data_providers import MarketDataProvider
from copinanceos.infrastructure.workflows import StaticWorkflowExecutor


@pytest.mark.unit
class TestStaticWorkflowExecutor:
    """Test StaticWorkflowExecutor."""

    def test_get_workflow_type(self) -> None:
        """Test that get_workflow_type returns 'stock'."""
        executor = StaticWorkflowExecutor()
        assert executor.get_workflow_type() == "stock"

    async def test_validate_returns_true_for_static_workflow(self) -> None:
        """Test that validate returns True for stock workflow type."""
        executor = StaticWorkflowExecutor()
        research = Research(
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.LONG_TERM,
            workflow_type="stock",
        )
        result = await executor.validate(research)
        assert result is True

    async def test_validate_returns_false_for_non_static_workflow(self) -> None:
        """Test that validate returns False for non-stock workflow types."""
        executor = StaticWorkflowExecutor()
        research = Research(
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.LONG_TERM,
            workflow_type="agent",
        )
        result = await executor.validate(research)
        assert result is False

    async def test_execute_returns_correct_results_structure(self) -> None:
        """Test that execute returns correct results structure."""
        # Mock dependencies
        mock_stock_use_case = AsyncMock(spec=GetStockUseCase)
        mock_stock_use_case.execute = AsyncMock(
            return_value=GetStockResponse(
                stock=Stock(
                    symbol="AAPL",
                    name="Apple Inc.",
                    exchange="NASDAQ",
                    sector="Technology",
                    industry="Consumer Electronics",
                )
            )
        )

        mock_market_provider = AsyncMock(spec=MarketDataProvider)
        mock_market_provider.get_quote = AsyncMock(
            return_value={
                "symbol": "AAPL",
                "current_price": Decimal("180.00"),
                "previous_close": Decimal("175.00"),
                "open": Decimal("176.00"),
                "high": Decimal("181.00"),
                "low": Decimal("175.50"),
                "volume": 50000000,
                "currency": "USD",
                "exchange": "NASDAQ",
            }
        )
        mock_market_provider.get_historical_data = AsyncMock(return_value=[])

        # Create minimal fundamentals for testing
        minimal_fundamentals = StockFundamentals(
            symbol="AAPL",
            company_name="Apple Inc.",
            provider="test_provider",
            data_as_of=datetime(2024, 1, 1),
        )

        mock_fundamentals_use_case = AsyncMock(spec=ResearchStockFundamentalsUseCase)
        mock_fundamentals_use_case.execute = AsyncMock(
            return_value=ResearchStockFundamentalsResponse(fundamentals=minimal_fundamentals)
        )

        executor = StaticWorkflowExecutor(
            get_stock_use_case=mock_stock_use_case,
            market_data_provider=mock_market_provider,
            fundamentals_use_case=mock_fundamentals_use_case,
        )

        research = Research(
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.SHORT_TERM,
            workflow_type="stock",
            parameters={"key": "value"},
        )
        context = {"context_key": "context_value"}

        results = await executor.execute(research, context)

        assert results["workflow_type"] == "stock"
        assert results["stock_symbol"] == "AAPL"
        assert results["timeframe"] == "short_term"
        assert results["analysis_type"] == "comprehensive_static"
        assert "execution_timestamp" in results
        assert "stock_info" in results
        assert "current_quote" in results
        assert "historical_data" in results
        assert "fundamentals" in results
        assert "analysis" in results
        assert "summary" in results
        assert results["status"] == "completed"
        assert "Stock workflow executed successfully" in results["message"]

    async def test_execute_with_different_timeframes(self) -> None:
        """Test execute with different timeframes."""
        # Mock dependencies
        mock_stock_use_case = AsyncMock(spec=GetStockUseCase)
        mock_stock_use_case.execute = AsyncMock(return_value=GetStockResponse(stock=None))

        mock_market_provider = AsyncMock(spec=MarketDataProvider)
        mock_market_provider.get_quote = AsyncMock(return_value={"symbol": "MSFT"})
        mock_market_provider.get_historical_data = AsyncMock(return_value=[])

        # Create minimal fundamentals for testing
        minimal_fundamentals = StockFundamentals(
            symbol="MSFT",
            company_name="Microsoft Corporation",
            provider="test_provider",
            data_as_of=datetime(2024, 1, 1),
        )

        mock_fundamentals_use_case = AsyncMock(spec=ResearchStockFundamentalsUseCase)
        mock_fundamentals_use_case.execute = AsyncMock(
            return_value=ResearchStockFundamentalsResponse(fundamentals=minimal_fundamentals)
        )

        executor = StaticWorkflowExecutor(
            get_stock_use_case=mock_stock_use_case,
            market_data_provider=mock_market_provider,
            fundamentals_use_case=mock_fundamentals_use_case,
        )

        for timeframe in ResearchTimeframe:
            research = Research(
                stock_symbol="MSFT",
                timeframe=timeframe,
                workflow_type="stock",
            )
            results = await executor.execute(research, {})
            assert results["timeframe"] == timeframe.value
            assert results["stock_symbol"] == "MSFT"

    async def test_execute_handles_missing_dependencies(self) -> None:
        """Test that execute handles missing dependencies gracefully."""
        executor = StaticWorkflowExecutor()  # No dependencies provided

        research = Research(
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
        )

        results = await executor.execute(research, {})

        assert results["workflow_type"] == "stock"
        assert results["stock_symbol"] == "AAPL"
        assert "stock_info" in results
        assert "current_quote" in results
        assert "fundamentals" in results
        # Should still complete even with missing dependencies
        assert results["status"] == "completed"

    async def test_execute_handles_errors_gracefully(self) -> None:
        """Test that execute handles errors gracefully by continuing execution."""
        mock_market_provider = AsyncMock(spec=MarketDataProvider)
        mock_market_provider.get_quote = AsyncMock(side_effect=Exception("API Error"))
        mock_market_provider.get_historical_data = AsyncMock(return_value=[])

        executor = StaticWorkflowExecutor(market_data_provider=mock_market_provider)

        research = Research(
            stock_symbol="INVALID",
            timeframe=ResearchTimeframe.SHORT_TERM,
            workflow_type="stock",
        )

        results = await executor.execute(research, {})

        assert results["workflow_type"] == "stock"
        # Workflow continues even when individual steps fail
        assert results["status"] == "completed"
        # Error is captured in the current_quote section
        assert "current_quote" in results
        assert "error" in results["current_quote"]
        assert "API Error" in results["current_quote"]["error"]


@pytest.mark.unit
class TestStaticWorkflowFundamentals:
    """Test that stock workflow includes full fundamentals data."""

    def _create_full_fundamentals(self) -> StockFundamentals:
        """Create full StockFundamentals with all data for testing."""
        period = FinancialStatementPeriod(
            period_end_date=datetime(2023, 12, 31),
            period_type="annual",
            fiscal_year=2023,
            fiscal_quarter=None,
        )

        income = IncomeStatement(
            period=period,
            total_revenue=Decimal("394328000000"),
            cost_of_revenue=Decimal("223546000000"),
            gross_profit=Decimal("170782000000"),
            operating_expenses=Decimal("51345000000"),
            operating_income=Decimal("119437000000"),
            interest_expense=Decimal("1003000000"),
            income_before_tax=Decimal("123136000000"),
            income_tax_expense=Decimal("19300000000"),
            net_income=Decimal("103847000000"),
            earnings_per_share=Decimal("6.66"),
            diluted_eps=Decimal("6.66"),
            shares_outstanding=15587200000,
            diluted_shares=15587200000,
            metadata={"source": "test"},
        )

        balance = BalanceSheet(
            period=period,
            cash_and_cash_equivalents=Decimal("29898000000"),
            short_term_investments=Decimal("31594000000"),
            accounts_receivable=Decimal("29508000000"),
            inventory=Decimal("6331000000"),
            current_assets=Decimal("143566000000"),
            property_plant_equipment=Decimal("43654000000"),
            long_term_investments=Decimal("100544000000"),
            total_assets=Decimal("352755000000"),
            accounts_payable=Decimal("54879000000"),
            short_term_debt=Decimal("11128000000"),
            current_liabilities=Decimal("133973000000"),
            long_term_debt=Decimal("95281000000"),
            total_liabilities=Decimal("290437000000"),
            common_stock=Decimal("64849000000"),
            retained_earnings=Decimal("-2140000000"),
            total_equity=Decimal("62318000000"),
            total_liabilities_and_equity=Decimal("352755000000"),
            metadata={"source": "test"},
        )

        cashflow = CashFlowStatement(
            period=period,
            net_income=Decimal("103847000000"),
            depreciation_amortization=Decimal("11050000000"),
            stock_based_compensation=Decimal("10300000000"),
            changes_in_working_capital=Decimal("-1000000000"),
            operating_cash_flow=Decimal("110543000000"),
            capital_expenditures=Decimal("-10982000000"),
            investments=Decimal("-5000000000"),
            investing_cash_flow=Decimal("-15982000000"),
            debt_issued=Decimal("10000000000"),
            debt_repaid=Decimal("-5000000000"),
            dividends_paid=Decimal("-15000000000"),
            share_repurchases=Decimal("-77500000000"),
            share_issuance=Decimal("1000000000"),
            financing_cash_flow=Decimal("-77500000000"),
            net_change_in_cash=Decimal("16961000000"),
            free_cash_flow=Decimal("99561000000"),
            metadata={"source": "test"},
        )

        ratios = FinancialRatios(
            gross_margin=Decimal("43.3"),
            operating_margin=Decimal("30.3"),
            net_margin=Decimal("26.3"),
            return_on_assets=Decimal("29.4"),
            return_on_equity=Decimal("166.6"),
            current_ratio=Decimal("1.07"),
            quick_ratio=Decimal("0.95"),
            debt_to_equity=Decimal("1.53"),
            price_to_earnings=Decimal("28.5"),
            metadata={"source": "test"},
        )

        return StockFundamentals(
            symbol="AAPL",
            company_name="Apple Inc.",
            sector="Technology",
            industry="Consumer Electronics",
            income_statements=[income],
            balance_sheets=[balance],
            cash_flow_statements=[cashflow],
            ratios=ratios,
            market_cap=Decimal("3000000000000"),
            enterprise_value=Decimal("3100000000000"),
            current_price=Decimal("180.00"),
            shares_outstanding=15587200000,
            float_shares=15500000000,
            provider="test_provider",
            data_as_of=datetime(2024, 1, 1),
            fiscal_year_end="September",
            currency="USD",
            metadata={"source": "test"},
        )

    async def test_static_workflow_includes_full_fundamentals(self) -> None:
        """Test that static workflow includes full financial statements."""
        mock_stock_use_case = AsyncMock(spec=GetStockUseCase)
        mock_stock_use_case.execute = AsyncMock(return_value=GetStockResponse(stock=None))

        mock_market_provider = AsyncMock(spec=MarketDataProvider)
        mock_market_provider.get_quote = AsyncMock(return_value={"symbol": "AAPL"})
        mock_market_provider.get_historical_data = AsyncMock(return_value=[])

        mock_fundamentals_use_case = AsyncMock(spec=ResearchStockFundamentalsUseCase)
        fundamentals = self._create_full_fundamentals()
        mock_fundamentals_use_case.execute = AsyncMock(
            return_value=ResearchStockFundamentalsResponse(fundamentals=fundamentals)
        )

        executor = StaticWorkflowExecutor(
            get_stock_use_case=mock_stock_use_case,
            market_data_provider=mock_market_provider,
            fundamentals_use_case=mock_fundamentals_use_case,
        )

        research = Research(
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.LONG_TERM,
            workflow_type="stock",
        )
        context = {}

        results = await executor.execute(research, context)

        # Verify fundamentals section includes full financial statements
        assert "fundamentals" in results
        fundamentals_data = results["fundamentals"]
        assert fundamentals_data["company_name"] == "Apple Inc."
        assert fundamentals_data["sector"] == "Technology"
        assert "latest_income_statement" in fundamentals_data
        assert "latest_balance_sheet" in fundamentals_data
        assert "latest_cash_flow_statement" in fundamentals_data
        assert "ratios" in fundamentals_data

        # Verify income statement data
        income = fundamentals_data["latest_income_statement"]
        assert income["total_revenue"] == "394328000000"
        assert income["net_income"] == "103847000000"

        # Verify balance sheet data
        balance = fundamentals_data["latest_balance_sheet"]
        assert balance["total_assets"] == "352755000000"
        assert balance["total_equity"] == "62318000000"

        # Verify cash flow statement data
        cashflow = fundamentals_data["latest_cash_flow_statement"]
        assert cashflow["operating_cash_flow"] == "110543000000"
        assert cashflow["free_cash_flow"] == "99561000000"
