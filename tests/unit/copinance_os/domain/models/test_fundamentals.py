"""Unit tests for fundamentals domain models."""

from datetime import datetime
from decimal import Decimal

import pytest

from copinance_os.domain.models.fundamentals import (
    BalanceSheet,
    CashFlowStatement,
    FinancialRatios,
    FinancialStatementPeriod,
    IncomeStatement,
    StockFundamentals,
)


@pytest.mark.unit
class TestFinancialStatementPeriod:
    """Test FinancialStatementPeriod value object."""

    def test_create_annual_period(self) -> None:
        """Test creating an annual period."""
        period = FinancialStatementPeriod(
            period_end_date=datetime(2023, 12, 31),
            period_type="annual",
            fiscal_year=2023,
        )

        assert period.period_end_date == datetime(2023, 12, 31)
        assert period.period_type == "annual"
        assert period.fiscal_year == 2023
        assert period.fiscal_quarter is None

    def test_create_quarterly_period(self) -> None:
        """Test creating a quarterly period."""
        period = FinancialStatementPeriod(
            period_end_date=datetime(2023, 3, 31),
            period_type="quarterly",
            fiscal_year=2023,
            fiscal_quarter=1,
        )

        assert period.period_end_date == datetime(2023, 3, 31)
        assert period.period_type == "quarterly"
        assert period.fiscal_year == 2023
        assert period.fiscal_quarter == 1


@pytest.mark.unit
class TestIncomeStatement:
    """Test IncomeStatement value object."""

    def test_create_income_statement(self) -> None:
        """Test creating an income statement."""
        period = FinancialStatementPeriod(
            period_end_date=datetime(2023, 12, 31),
            period_type="annual",
            fiscal_year=2023,
        )
        income_statement = IncomeStatement(
            period=period,
            total_revenue=Decimal("1000000"),
            cost_of_revenue=Decimal("600000"),
            gross_profit=Decimal("400000"),
            net_income=Decimal("200000"),
        )

        assert income_statement.period == period
        assert income_statement.total_revenue == Decimal("1000000")
        assert income_statement.gross_profit == Decimal("400000")
        assert income_statement.net_income == Decimal("200000")
        assert income_statement.metadata == {}

    def test_income_statement_with_metadata(self) -> None:
        """Test income statement with metadata."""
        period = FinancialStatementPeriod(
            period_end_date=datetime(2023, 12, 31),
            period_type="annual",
            fiscal_year=2023,
        )
        income_statement = IncomeStatement(
            period=period,
            total_revenue=Decimal("1000000"),
            metadata={"source": "SEC", "filing_type": "10-K"},
        )

        assert income_statement.metadata == {"source": "SEC", "filing_type": "10-K"}


@pytest.mark.unit
class TestBalanceSheet:
    """Test BalanceSheet value object."""

    def test_create_balance_sheet(self) -> None:
        """Test creating a balance sheet."""
        period = FinancialStatementPeriod(
            period_end_date=datetime(2023, 12, 31),
            period_type="annual",
            fiscal_year=2023,
        )
        balance_sheet = BalanceSheet(
            period=period,
            cash_and_cash_equivalents=Decimal("50000"),
            total_assets=Decimal("1000000"),
            total_liabilities=Decimal("600000"),
            total_equity=Decimal("400000"),
        )

        assert balance_sheet.period == period
        assert balance_sheet.cash_and_cash_equivalents == Decimal("50000")
        assert balance_sheet.total_assets == Decimal("1000000")
        assert balance_sheet.total_liabilities == Decimal("600000")
        assert balance_sheet.total_equity == Decimal("400000")


@pytest.mark.unit
class TestCashFlowStatement:
    """Test CashFlowStatement value object."""

    def test_create_cash_flow_statement(self) -> None:
        """Test creating a cash flow statement."""
        period = FinancialStatementPeriod(
            period_end_date=datetime(2023, 12, 31),
            period_type="annual",
            fiscal_year=2023,
        )
        cash_flow = CashFlowStatement(
            period=period,
            net_income=Decimal("200000"),
            operating_cash_flow=Decimal("250000"),
            investing_cash_flow=Decimal("-50000"),
            financing_cash_flow=Decimal("-20000"),
            free_cash_flow=Decimal("200000"),
        )

        assert cash_flow.period == period
        assert cash_flow.net_income == Decimal("200000")
        assert cash_flow.operating_cash_flow == Decimal("250000")
        assert cash_flow.free_cash_flow == Decimal("200000")


@pytest.mark.unit
class TestFinancialRatios:
    """Test FinancialRatios value object."""

    def test_create_financial_ratios(self) -> None:
        """Test creating financial ratios."""
        ratios = FinancialRatios(
            gross_margin=Decimal("40.0"),
            operating_margin=Decimal("20.0"),
            net_margin=Decimal("15.0"),
            return_on_equity=Decimal("25.0"),
            current_ratio=Decimal("2.5"),
            debt_to_equity=Decimal("0.5"),
        )

        assert ratios.gross_margin == Decimal("40.0")
        assert ratios.operating_margin == Decimal("20.0")
        assert ratios.net_margin == Decimal("15.0")
        assert ratios.return_on_equity == Decimal("25.0")
        assert ratios.current_ratio == Decimal("2.5")
        assert ratios.debt_to_equity == Decimal("0.5")


@pytest.mark.unit
class TestStockFundamentals:
    """Test StockFundamentals entity."""

    def test_create_stock_fundamentals(self) -> None:
        """Test creating stock fundamentals."""
        fundamentals = StockFundamentals(
            symbol="AAPL",
            company_name="Apple Inc.",
            provider="yfinance",
            data_as_of=datetime(2023, 12, 31),
        )

        assert fundamentals.symbol == "AAPL"
        assert fundamentals.company_name == "Apple Inc."
        assert fundamentals.provider == "yfinance"
        assert fundamentals.income_statements == []
        assert fundamentals.balance_sheets == []
        assert fundamentals.cash_flow_statements == []

    def test_stock_fundamentals_with_financial_statements(self) -> None:
        """Test stock fundamentals with financial statements."""
        period = FinancialStatementPeriod(
            period_end_date=datetime(2023, 12, 31),
            period_type="annual",
            fiscal_year=2023,
        )
        income_statement = IncomeStatement(
            period=period,
            total_revenue=Decimal("1000000"),
            net_income=Decimal("200000"),
        )
        balance_sheet = BalanceSheet(
            period=period,
            total_assets=Decimal("1000000"),
            total_equity=Decimal("400000"),
        )

        fundamentals = StockFundamentals(
            symbol="AAPL",
            provider="yfinance",
            data_as_of=datetime(2023, 12, 31),
            income_statements=[income_statement],
            balance_sheets=[balance_sheet],
        )

        assert len(fundamentals.income_statements) == 1
        assert len(fundamentals.balance_sheets) == 1
        assert fundamentals.income_statements[0] == income_statement
        assert fundamentals.balance_sheets[0] == balance_sheet

    def test_stock_fundamentals_with_ratios(self) -> None:
        """Test stock fundamentals with financial ratios."""
        ratios = FinancialRatios(
            gross_margin=Decimal("40.0"),
            net_margin=Decimal("15.0"),
        )

        fundamentals = StockFundamentals(
            symbol="AAPL",
            provider="yfinance",
            data_as_of=datetime(2023, 12, 31),
            ratios=ratios,
        )

        assert fundamentals.ratios == ratios
        assert fundamentals.ratios.gross_margin == Decimal("40.0")
