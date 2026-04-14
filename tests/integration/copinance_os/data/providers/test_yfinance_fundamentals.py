"""Integration tests for yfinance fundamentals data provider."""

from decimal import Decimal

import pytest

from copinance_os.data.providers.yfinance import (
    YFinanceFundamentalProvider,
)
from copinance_os.domain.exceptions import (
    DataProviderError,
    InvalidStockSymbolError,
    ValidationError,
)
from copinance_os.domain.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    FinancialRatios,
    IncomeStatement,
    StockFundamentals,
)
from copinance_os.research.workflows.fundamentals import (
    GetStockFundamentalsRequest,
    GetStockFundamentalsUseCase,
)


def _maybe_skip_yfinance_transient_error(exc: BaseException) -> None:
    """Skip when Yahoo/yfinance is unreachable or returns transient errors (integration only)."""
    if isinstance(exc, (ValueError, OSError, ConnectionError)):
        msg = str(exc)
        if "Failed to fetch" in msg or "Connection" in msg or "curl" in msg:
            pytest.skip(f"Network unavailable or transient error: {exc}")


@pytest.mark.integration
class TestYFinanceFundamentalProvider:
    """Integration tests for YFinanceFundamentalProvider."""

    @pytest.fixture(scope="class")
    def provider(self) -> YFinanceFundamentalProvider:
        """Provide a YFinanceFundamentalProvider instance with caching enabled.

        Using class scope so all tests in this class share the same provider instance
        and benefit from caching, reducing API calls and improving test reliability.
        """
        return YFinanceFundamentalProvider(cache_ttl_seconds=3600)

    @pytest.fixture(scope="class")
    async def cached_fundamentals_aapl_annual(
        self, provider: YFinanceFundamentalProvider
    ) -> StockFundamentals:
        """Pre-fetch and cache AAPL annual fundamentals for reuse across tests.

        This fixture ensures all tests using AAPL annual data share the same cached result,
        significantly reducing API calls and test execution time.
        """
        try:
            return await provider.get_detailed_fundamentals(
                symbol="AAPL",
                periods=3,  # Use 3 periods to cover most test needs
                period_type="annual",
            )
        except (ValueError, OSError, ConnectionError) as e:
            _maybe_skip_yfinance_transient_error(e)
            raise

    @pytest.mark.asyncio
    async def test_provider_availability(self, provider: YFinanceFundamentalProvider) -> None:
        """Test that the provider is available (skipped when network/Yahoo is unreachable)."""
        assert provider.get_provider_name() == "yfinance"
        is_available = await provider.is_available()
        if not is_available:
            pytest.skip(
                "yfinance provider unavailable (yfinance not installed, or network/Yahoo unreachable)"
            )
        assert is_available is True

    @pytest.mark.asyncio
    async def test_get_detailed_fundamentals_annual(
        self, provider: YFinanceFundamentalProvider
    ) -> None:
        """Test retrieving detailed fundamentals with annual data."""
        try:
            fundamentals = await provider.get_detailed_fundamentals(
                symbol="AAPL",
                periods=3,
                period_type="annual",
            )
        except (ValueError, OSError, ConnectionError) as e:
            _maybe_skip_yfinance_transient_error(e)
            raise

        # Basic assertions
        assert isinstance(fundamentals, StockFundamentals)
        assert fundamentals.symbol == "AAPL"
        assert fundamentals.provider == "yfinance"
        assert fundamentals.data_as_of is not None

        # Company information
        assert fundamentals.company_name is not None
        assert len(fundamentals.company_name) > 0

        # Financial statements should be populated
        assert len(fundamentals.income_statements) > 0
        assert len(fundamentals.balance_sheets) > 0
        assert len(fundamentals.cash_flow_statements) > 0

        # Most recent period should be first
        if fundamentals.income_statements:
            latest_income = fundamentals.income_statements[0]
            assert latest_income.period.period_type == "annual"
            assert latest_income.period.fiscal_year is not None

        # Ratios should be calculated if we have data
        if fundamentals.ratios:
            assert fundamentals.ratios is not None

    @pytest.mark.asyncio
    async def test_get_detailed_fundamentals_quarterly(
        self, provider: YFinanceFundamentalProvider
    ) -> None:
        """Test retrieving detailed fundamentals with quarterly data."""
        try:
            fundamentals = await provider.get_detailed_fundamentals(
                symbol="MSFT",
                periods=4,
                period_type="quarterly",
            )
        except (ValueError, OSError, ConnectionError) as e:
            _maybe_skip_yfinance_transient_error(e)
            raise

        assert isinstance(fundamentals, StockFundamentals)
        assert fundamentals.symbol == "MSFT"

        # Should have quarterly data
        if fundamentals.income_statements:
            latest_income = fundamentals.income_statements[0]
            assert latest_income.period.period_type == "quarterly"
            assert latest_income.period.fiscal_quarter is not None
            assert 1 <= latest_income.period.fiscal_quarter <= 4

    @pytest.mark.asyncio
    async def test_income_statement_structure(
        self,
        provider: YFinanceFundamentalProvider,
        cached_fundamentals_aapl_annual: StockFundamentals,
    ) -> None:
        """Test that income statements have proper structure."""
        fundamentals = cached_fundamentals_aapl_annual

        assert len(fundamentals.income_statements) > 0

        for income in fundamentals.income_statements:
            assert isinstance(income, IncomeStatement)
            assert income.period is not None
            assert income.period.period_end_date is not None
            assert income.period.fiscal_year is not None

            # At least one of these should be populated for a valid company
            assert (
                income.total_revenue is not None
                or income.net_income is not None
                or income.operating_income is not None
            )

    @pytest.mark.asyncio
    async def test_balance_sheet_structure(
        self,
        provider: YFinanceFundamentalProvider,
        cached_fundamentals_aapl_annual: StockFundamentals,
    ) -> None:
        """Test that balance sheets have proper structure."""
        fundamentals = cached_fundamentals_aapl_annual

        assert len(fundamentals.balance_sheets) > 0

        for balance in fundamentals.balance_sheets:
            assert isinstance(balance, BalanceSheet)
            assert balance.period is not None

            # At least one of these should be populated
            assert (
                balance.total_assets is not None
                or balance.total_equity is not None
                or balance.cash_and_cash_equivalents is not None
            )

    @pytest.mark.asyncio
    async def test_cash_flow_statement_structure(
        self,
        provider: YFinanceFundamentalProvider,
        cached_fundamentals_aapl_annual: StockFundamentals,
    ) -> None:
        """Test that cash flow statements have proper structure."""
        fundamentals = cached_fundamentals_aapl_annual

        assert len(fundamentals.cash_flow_statements) > 0

        for cashflow in fundamentals.cash_flow_statements:
            assert isinstance(cashflow, CashFlowStatement)
            assert cashflow.period is not None

            # At least one of these should be populated
            assert (
                cashflow.operating_cash_flow is not None
                or cashflow.net_income is not None
                or cashflow.free_cash_flow is not None
            )

    @pytest.mark.asyncio
    async def test_financial_ratios_calculation(
        self,
        provider: YFinanceFundamentalProvider,
        cached_fundamentals_aapl_annual: StockFundamentals,
    ) -> None:
        """Test that financial ratios are calculated when data is available."""
        fundamentals = cached_fundamentals_aapl_annual

        # Ratios may or may not be calculated depending on available data
        if fundamentals.ratios:
            ratios = fundamentals.ratios
            assert isinstance(ratios, FinancialRatios)

            # If we have revenue and gross profit, gross margin should be calculated
            if (
                fundamentals.income_statements
                and fundamentals.income_statements[0].total_revenue
                and fundamentals.income_statements[0].gross_profit
            ) and ratios.gross_margin is not None:
                assert isinstance(ratios.gross_margin, Decimal)
                assert 0 <= ratios.gross_margin <= 100  # Percentage

    @pytest.mark.asyncio
    async def test_market_data_included(
        self,
        provider: YFinanceFundamentalProvider,
        cached_fundamentals_aapl_annual: StockFundamentals,
    ) -> None:
        """Test that market data is included when available."""
        fundamentals = cached_fundamentals_aapl_annual

        # Market data may or may not be available, but if it is, it should be valid
        if fundamentals.market_cap is not None:
            assert isinstance(fundamentals.market_cap, Decimal)
            assert fundamentals.market_cap > 0

        if fundamentals.current_price is not None:
            assert isinstance(fundamentals.current_price, Decimal)
            assert fundamentals.current_price > 0

        if fundamentals.shares_outstanding is not None:
            assert isinstance(fundamentals.shares_outstanding, int)
            assert fundamentals.shares_outstanding > 0

    @pytest.mark.asyncio
    async def test_invalid_symbol_handling(self, provider: YFinanceFundamentalProvider) -> None:
        """Test that invalid symbols are handled gracefully."""
        with pytest.raises(DataProviderError, match="Failed to fetch detailed fundamentals"):
            await provider.get_detailed_fundamentals(
                symbol="INVALID_SYMBOL_XYZ123",
                periods=1,
                period_type="annual",
            )

    @pytest.mark.asyncio
    async def test_periods_limit(
        self,
        provider: YFinanceFundamentalProvider,
        cached_fundamentals_aapl_annual: StockFundamentals,
    ) -> None:
        """Test that the periods parameter limits the number of periods returned."""
        # Use cached data but verify it respects the periods limit
        fundamentals = cached_fundamentals_aapl_annual

        # Should not exceed requested periods (cached data has 3 periods, but we verify structure)
        assert len(fundamentals.income_statements) <= 3
        assert len(fundamentals.balance_sheets) <= 3
        assert len(fundamentals.cash_flow_statements) <= 3

    @pytest.mark.asyncio
    async def test_statements_chronological_order(
        self,
        provider: YFinanceFundamentalProvider,
        cached_fundamentals_aapl_annual: StockFundamentals,
    ) -> None:
        """Test that financial statements are in reverse chronological order (most recent first)."""
        fundamentals = cached_fundamentals_aapl_annual

        # Check income statements are in reverse chronological order
        if len(fundamentals.income_statements) > 1:
            for i in range(len(fundamentals.income_statements) - 1):
                current = fundamentals.income_statements[i].period.period_end_date
                next_period = fundamentals.income_statements[i + 1].period.period_end_date
                assert current >= next_period, "Statements should be most recent first"

    @pytest.mark.asyncio
    async def test_all_income_statement_fields_populated(
        self,
        provider: YFinanceFundamentalProvider,
        cached_fundamentals_aapl_annual: StockFundamentals,
    ) -> None:
        """Test that all available income statement fields are populated from yfinance data."""
        fundamentals = cached_fundamentals_aapl_annual

        assert len(fundamentals.income_statements) > 0, "Should have at least one income statement"
        income = fundamentals.income_statements[0]

        # Required fields (should always be present)
        assert income.period is not None
        assert income.period.period_end_date is not None
        assert income.period.period_type is not None
        assert income.period.fiscal_year is not None

        # Core income statement fields that should be available from yfinance for AAPL
        # These are common fields that yfinance typically provides
        assert income.total_revenue is not None, "total_revenue should be populated"
        assert income.total_revenue > 0, "total_revenue should be positive"
        assert income.net_income is not None, "net_income should be populated"
        assert income.operating_income is not None, "operating_income should be populated"
        assert income.gross_profit is not None, "gross_profit should be populated"
        assert income.cost_of_revenue is not None, "cost_of_revenue should be populated"

    @pytest.mark.asyncio
    async def test_all_balance_sheet_fields_populated(
        self,
        provider: YFinanceFundamentalProvider,
        cached_fundamentals_aapl_annual: StockFundamentals,
    ) -> None:
        """Test that all available balance sheet fields are populated from yfinance data."""
        fundamentals = cached_fundamentals_aapl_annual

        assert len(fundamentals.balance_sheets) > 0, "Should have at least one balance sheet"
        balance = fundamentals.balance_sheets[0]

        # Required fields
        assert balance.period is not None
        assert balance.period.period_end_date is not None

        # Core balance sheet fields that should be available from yfinance for AAPL
        assert balance.total_assets is not None, "total_assets should be populated"
        assert balance.total_assets > 0, "total_assets should be positive"
        assert balance.total_equity is not None, "total_equity should be populated"
        assert (
            balance.cash_and_cash_equivalents is not None
        ), "cash_and_cash_equivalents should be populated"
        assert balance.current_assets is not None, "current_assets should be populated"
        assert balance.current_liabilities is not None, "current_liabilities should be populated"
        assert balance.accounts_receivable is not None, "accounts_receivable should be populated"
        assert balance.inventory is not None, "inventory should be populated"
        assert (
            balance.property_plant_equipment is not None
        ), "property_plant_equipment should be populated"
        assert balance.accounts_payable is not None, "accounts_payable should be populated"
        assert balance.short_term_debt is not None, "short_term_debt should be populated"
        assert balance.long_term_debt is not None, "long_term_debt should be populated"
        assert balance.common_stock is not None, "common_stock should be populated"

    @pytest.mark.asyncio
    async def test_all_cash_flow_statement_fields_populated(
        self,
        provider: YFinanceFundamentalProvider,
        cached_fundamentals_aapl_annual: StockFundamentals,
    ) -> None:
        """Test that all available cash flow statement fields are populated from yfinance data."""
        fundamentals = cached_fundamentals_aapl_annual

        assert (
            len(fundamentals.cash_flow_statements) > 0
        ), "Should have at least one cash flow statement"
        cashflow = fundamentals.cash_flow_statements[0]

        # Required fields
        assert cashflow.period is not None
        assert cashflow.period.period_end_date is not None

        # Core cash flow fields that should be available from yfinance for AAPL
        assert cashflow.operating_cash_flow is not None, "operating_cash_flow should be populated"
        assert cashflow.free_cash_flow is not None, "free_cash_flow should be populated"
        assert cashflow.investing_cash_flow is not None, "investing_cash_flow should be populated"
        assert cashflow.financing_cash_flow is not None, "financing_cash_flow should be populated"
        assert (
            cashflow.depreciation_amortization is not None
        ), "depreciation_amortization should be populated"
        assert (
            cashflow.stock_based_compensation is not None
        ), "stock_based_compensation should be populated"
        assert (
            cashflow.changes_in_working_capital is not None
        ), "changes_in_working_capital should be populated"
        assert cashflow.capital_expenditures is not None, "capital_expenditures should be populated"

    @pytest.mark.asyncio
    async def test_all_financial_ratios_calculated(
        self,
        provider: YFinanceFundamentalProvider,
        cached_fundamentals_aapl_annual: StockFundamentals,
    ) -> None:
        """Test that all available financial ratios are calculated from actual data."""
        fundamentals = cached_fundamentals_aapl_annual

        assert fundamentals.ratios is not None, "ratios should be calculated"
        ratios = fundamentals.ratios

        # Profitability ratios (should be calculated if revenue and income data available)
        assert ratios.gross_margin is not None, "gross_margin should be calculated"
        assert isinstance(ratios.gross_margin, Decimal)
        assert 0 <= ratios.gross_margin <= 100, "gross_margin should be a percentage"

        assert ratios.operating_margin is not None, "operating_margin should be calculated"
        assert isinstance(ratios.operating_margin, Decimal)
        assert 0 <= ratios.operating_margin <= 100, "operating_margin should be a percentage"

        assert ratios.net_margin is not None, "net_margin should be calculated"
        assert isinstance(ratios.net_margin, Decimal)
        assert 0 <= ratios.net_margin <= 100, "net_margin should be a percentage"

        # Return ratios
        assert ratios.return_on_assets is not None, "return_on_assets should be calculated"
        assert isinstance(ratios.return_on_assets, Decimal)

        assert ratios.return_on_equity is not None, "return_on_equity should be calculated"
        assert isinstance(ratios.return_on_equity, Decimal)

        # Liquidity ratios
        assert ratios.current_ratio is not None, "current_ratio should be calculated"
        assert isinstance(ratios.current_ratio, Decimal)
        assert ratios.current_ratio > 0, "current_ratio should be positive"

        assert ratios.quick_ratio is not None, "quick_ratio should be calculated"
        assert isinstance(ratios.quick_ratio, Decimal)

        assert ratios.cash_ratio is not None, "cash_ratio should be calculated"
        assert isinstance(ratios.cash_ratio, Decimal)

        # Leverage ratios
        assert ratios.debt_to_equity is not None, "debt_to_equity should be calculated"
        assert isinstance(ratios.debt_to_equity, Decimal)

        assert ratios.debt_to_assets is not None, "debt_to_assets should be calculated"
        assert isinstance(ratios.debt_to_assets, Decimal)

        assert ratios.equity_ratio is not None, "equity_ratio should be calculated"
        assert isinstance(ratios.equity_ratio, Decimal)

        # Efficiency ratios
        assert ratios.asset_turnover is not None, "asset_turnover should be calculated"
        assert isinstance(ratios.asset_turnover, Decimal)
        assert ratios.asset_turnover > 0, "asset_turnover should be positive"

    @pytest.mark.asyncio
    async def test_all_stock_fundamentals_fields_populated(
        self,
        provider: YFinanceFundamentalProvider,
        cached_fundamentals_aapl_annual: StockFundamentals,
    ) -> None:
        """Test that all available StockFundamentals fields are populated from yfinance data."""
        fundamentals = cached_fundamentals_aapl_annual

        # Required fields
        assert fundamentals.symbol == "AAPL"
        assert fundamentals.provider == "yfinance"
        assert fundamentals.data_as_of is not None

        # Company information (should be available from yfinance)
        assert fundamentals.company_name is not None, "company_name should be populated"
        assert len(fundamentals.company_name) > 0, "company_name should not be empty"
        assert fundamentals.sector is not None, "sector should be populated"
        assert fundamentals.industry is not None, "industry should be populated"

        # Market data (should be available from yfinance for AAPL)
        assert fundamentals.market_cap is not None, "market_cap should be populated"
        assert fundamentals.market_cap > 0, "market_cap should be positive"
        assert fundamentals.current_price is not None, "current_price should be populated"
        assert fundamentals.current_price > 0, "current_price should be positive"
        assert fundamentals.shares_outstanding is not None, "shares_outstanding should be populated"
        assert fundamentals.shares_outstanding > 0, "shares_outstanding should be positive"

        # Enterprise value may or may not be available
        # Currency and fiscal year end should be available
        assert fundamentals.currency is not None, "currency should be populated"
        assert len(fundamentals.currency) > 0, "currency should not be empty"


@pytest.mark.integration
class TestGetStockFundamentalsUseCase:
    """Integration tests for GetStockFundamentalsUseCase with yfinance."""

    @pytest.fixture(scope="class")
    def use_case(self) -> GetStockFundamentalsUseCase:
        """Provide a GetStockFundamentalsUseCase instance with caching enabled.

        Using class scope so all tests in this class share the same provider instance
        and benefit from caching, reducing API calls and improving test reliability.
        """
        provider = YFinanceFundamentalProvider(cache_ttl_seconds=3600)
        return GetStockFundamentalsUseCase(provider)

    @pytest.mark.asyncio
    async def test_research_fundamentals_use_case(
        self, use_case: GetStockFundamentalsUseCase
    ) -> None:
        """Test the complete use case for researching stock fundamentals."""
        request = GetStockFundamentalsRequest(
            symbol="AAPL",
            periods=3,
            period_type="annual",
        )

        try:
            response = await use_case.execute(request)
        except (ValueError, OSError, ConnectionError) as e:
            _maybe_skip_yfinance_transient_error(e)
            raise

        assert response.fundamentals is not None
        assert response.fundamentals.symbol == "AAPL"
        assert len(response.fundamentals.income_statements) > 0

    @pytest.mark.asyncio
    async def test_use_case_validation_empty_symbol(
        self, use_case: GetStockFundamentalsUseCase
    ) -> None:
        """Test that empty symbol is rejected."""
        request = GetStockFundamentalsRequest(
            symbol="",
            periods=1,
            period_type="annual",
        )

        with pytest.raises(InvalidStockSymbolError, match="Symbol cannot be empty"):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_use_case_validation_invalid_period_type(
        self, use_case: GetStockFundamentalsUseCase
    ) -> None:
        """Test that invalid period type is rejected."""
        request = GetStockFundamentalsRequest(
            symbol="AAPL",
            periods=1,
            period_type="invalid",
        )

        with pytest.raises(ValidationError, match="Invalid period_type"):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_use_case_validation_invalid_periods(
        self, use_case: GetStockFundamentalsUseCase
    ) -> None:
        """Test that invalid periods count is rejected."""
        request = GetStockFundamentalsRequest(
            symbol="AAPL",
            periods=0,
            period_type="annual",
        )

        with pytest.raises(ValidationError, match="periods must be at least 1"):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_use_case_symbol_normalization(
        self, use_case: GetStockFundamentalsUseCase
    ) -> None:
        """Test that symbol is normalized to uppercase."""
        request = GetStockFundamentalsRequest(
            symbol="aapl",
            periods=1,
            period_type="annual",
        )

        try:
            response = await use_case.execute(request)
        except (ValueError, OSError, ConnectionError) as e:
            _maybe_skip_yfinance_transient_error(e)
            raise

        assert response.fundamentals.symbol == "AAPL"
