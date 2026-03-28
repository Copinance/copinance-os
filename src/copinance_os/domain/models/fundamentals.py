"""Stock fundamentals domain models."""

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from copinance_os.domain.models.base import Entity, ValueObject


class FinancialStatementPeriod(ValueObject):
    """Value object representing a financial statement period."""

    period_end_date: datetime = Field(..., description="Period end date")
    period_type: str = Field(..., description="Period type (annual or quarterly)")
    fiscal_year: int = Field(..., description="Fiscal year")
    fiscal_quarter: int | None = Field(
        None, description="Fiscal quarter (1-4) for quarterly periods"
    )


class IncomeStatement(ValueObject):
    """Value object representing income statement data for a period."""

    period: FinancialStatementPeriod = Field(..., description="Statement period")
    total_revenue: Decimal | None = Field(None, description="Total revenue/sales")
    cost_of_revenue: Decimal | None = Field(None, description="Cost of revenue/COGS")
    gross_profit: Decimal | None = Field(None, description="Gross profit")
    operating_expenses: Decimal | None = Field(None, description="Total operating expenses")
    operating_income: Decimal | None = Field(None, description="Operating income/EBIT")
    interest_expense: Decimal | None = Field(None, description="Interest expense")
    income_before_tax: Decimal | None = Field(
        None, description="Income before tax (also known as pretax income or earnings before tax)"
    )
    income_tax_expense: Decimal | None = Field(None, description="Income tax expense")
    net_income: Decimal | None = Field(None, description="Net income")
    earnings_per_share: Decimal | None = Field(None, description="Earnings per share (EPS)")
    diluted_eps: Decimal | None = Field(None, description="Diluted earnings per share")
    shares_outstanding: int | None = Field(None, description="Shares outstanding")
    diluted_shares: int | None = Field(None, description="Diluted shares outstanding")
    metadata: dict[str, str] = Field(
        default_factory=dict, description="Additional income statement metadata"
    )


class BalanceSheet(ValueObject):
    """Value object representing balance sheet data for a period."""

    period: FinancialStatementPeriod = Field(..., description="Statement period")
    # Assets
    cash_and_cash_equivalents: Decimal | None = Field(None, description="Cash and cash equivalents")
    short_term_investments: Decimal | None = Field(
        None,
        description="Short-term investments (marketable securities, available-for-sale securities)",
    )
    accounts_receivable: Decimal | None = Field(None, description="Accounts receivable")
    inventory: Decimal | None = Field(None, description="Inventory")
    current_assets: Decimal | None = Field(None, description="Total current assets")
    property_plant_equipment: Decimal | None = Field(
        None, description="Property, plant, and equipment (PP&E)"
    )
    long_term_investments: Decimal | None = Field(
        None,
        description="Long-term investments (investments in financial assets, advances, equity investments)",
    )
    total_assets: Decimal | None = Field(None, description="Total assets")
    # Liabilities
    accounts_payable: Decimal | None = Field(None, description="Accounts payable")
    short_term_debt: Decimal | None = Field(None, description="Short-term debt")
    current_liabilities: Decimal | None = Field(None, description="Total current liabilities")
    long_term_debt: Decimal | None = Field(None, description="Long-term debt")
    total_liabilities: Decimal | None = Field(
        None, description="Total liabilities (including minority interest if applicable)"
    )
    # Equity
    common_stock: Decimal | None = Field(None, description="Common stock")
    retained_earnings: Decimal | None = Field(None, description="Retained earnings")
    total_equity: Decimal | None = Field(None, description="Total equity")
    total_liabilities_and_equity: Decimal | None = Field(
        None, description="Total liabilities and equity"
    )
    metadata: dict[str, str] = Field(
        default_factory=dict, description="Additional balance sheet metadata"
    )


class CashFlowStatement(ValueObject):
    """Value object representing cash flow statement data for a period."""

    period: FinancialStatementPeriod = Field(..., description="Statement period")
    # Operating Activities
    net_income: Decimal | None = Field(None, description="Net income (starting point)")
    depreciation_amortization: Decimal | None = Field(
        None, description="Depreciation and amortization (D&A) - non-cash expenses"
    )
    stock_based_compensation: Decimal | None = Field(None, description="Stock-based compensation")
    changes_in_working_capital: Decimal | None = Field(
        None, description="Changes in working capital (current assets - current liabilities)"
    )
    operating_cash_flow: Decimal | None = Field(None, description="Cash from operating activities")
    # Investing Activities
    capital_expenditures: Decimal | None = Field(None, description="Capital expenditures (CapEx)")
    investments: Decimal | None = Field(
        None, description="Net investments (purchases/sales of investments and securities)"
    )
    investing_cash_flow: Decimal | None = Field(None, description="Cash from investing activities")
    # Financing Activities
    debt_issued: Decimal | None = Field(
        None, description="Proceeds from debt issuance (new debt raised)"
    )
    debt_repaid: Decimal | None = Field(
        None, description="Debt repayment (principal payments on debt)"
    )
    dividends_paid: Decimal | None = Field(None, description="Cash dividends paid to shareholders")
    share_repurchases: Decimal | None = Field(
        None, description="Share repurchases (treasury stock purchases, buybacks)"
    )
    share_issuance: Decimal | None = Field(
        None,
        description="Proceeds from share issuance (stock options exercised, new shares issued)",
    )
    financing_cash_flow: Decimal | None = Field(None, description="Cash from financing activities")
    # Net Change
    net_change_in_cash: Decimal | None = Field(
        None, description="Net change in cash and cash equivalents during the period"
    )
    free_cash_flow: Decimal | None = Field(None, description="Free cash flow (FCF)")
    metadata: dict[str, str] = Field(
        default_factory=dict, description="Additional cash flow metadata"
    )


class FinancialRatios(ValueObject):
    """Value object representing calculated financial ratios."""

    # Profitability Ratios
    gross_margin: Decimal | None = Field(None, description="Gross margin (%)")
    operating_margin: Decimal | None = Field(None, description="Operating margin (%)")
    net_margin: Decimal | None = Field(None, description="Net margin (%)")
    return_on_assets: Decimal | None = Field(None, description="Return on assets (ROA) (%)")
    return_on_equity: Decimal | None = Field(None, description="Return on equity (ROE) (%)")
    return_on_invested_capital: Decimal | None = Field(
        None, description="Return on invested capital (ROIC) (%)"
    )
    # Liquidity Ratios
    current_ratio: Decimal | None = Field(None, description="Current ratio")
    quick_ratio: Decimal | None = Field(None, description="Quick ratio (acid-test)")
    cash_ratio: Decimal | None = Field(None, description="Cash ratio")
    # Leverage Ratios
    debt_to_equity: Decimal | None = Field(None, description="Debt-to-equity ratio")
    debt_to_assets: Decimal | None = Field(None, description="Debt-to-assets ratio")
    equity_ratio: Decimal | None = Field(None, description="Equity ratio")
    interest_coverage: Decimal | None = Field(None, description="Interest coverage ratio")
    # Efficiency Ratios
    asset_turnover: Decimal | None = Field(None, description="Asset turnover ratio")
    inventory_turnover: Decimal | None = Field(None, description="Inventory turnover ratio")
    receivables_turnover: Decimal | None = Field(None, description="Receivables turnover ratio")
    # Valuation Ratios (may require market data)
    price_to_earnings: Decimal | None = Field(None, description="Price-to-earnings (P/E) ratio")
    price_to_book: Decimal | None = Field(None, description="Price-to-book (P/B) ratio")
    price_to_sales: Decimal | None = Field(None, description="Price-to-sales (P/S) ratio")
    price_to_free_cash_flow: Decimal | None = Field(
        None, description="Price-to-free-cash-flow ratio"
    )
    enterprise_value_to_ebitda: Decimal | None = Field(None, description="EV/EBITDA ratio")
    # Growth Rates (calculated from historical data)
    revenue_growth: Decimal | None = Field(None, description="Revenue growth rate (%)")
    earnings_growth: Decimal | None = Field(None, description="Earnings growth rate (%)")
    free_cash_flow_growth: Decimal | None = Field(
        None, description="Free cash flow growth rate (%)"
    )
    metadata: dict[str, str] = Field(default_factory=dict, description="Additional ratio metadata")


class StockFundamentals(Entity):
    """Entity representing comprehensive stock fundamentals.

    This model is provider-agnostic and represents detailed fundamental analysis
    data that can be sourced from any data provider (yfinance, SEC data vendors, Bloomberg, etc.).
    """

    symbol: str = Field(..., description="Stock ticker symbol")
    company_name: str | None = Field(None, description="Company name")
    sector: str | None = Field(None, description="Industry sector")
    industry: str | None = Field(None, description="Industry classification")
    # Financial Statements
    income_statements: list[IncomeStatement] = Field(
        default_factory=list, description="Historical income statements (most recent first)"
    )
    balance_sheets: list[BalanceSheet] = Field(
        default_factory=list, description="Historical balance sheets (most recent first)"
    )
    cash_flow_statements: list[CashFlowStatement] = Field(
        default_factory=list, description="Historical cash flow statements (most recent first)"
    )
    # Calculated Ratios (for most recent period)
    ratios: FinancialRatios | None = Field(
        None, description="Financial ratios for most recent period"
    )
    # Market Data (if available)
    market_cap: Decimal | None = Field(None, description="Market capitalization")
    enterprise_value: Decimal | None = Field(None, description="Enterprise value")
    current_price: Decimal | None = Field(None, description="Current stock price")
    # Additional Metrics
    shares_outstanding: int | None = Field(None, description="Shares outstanding")
    float_shares: int | None = Field(None, description="Float shares")
    # Data Source Information
    provider: str = Field(..., description="Data provider name")
    data_as_of: datetime = Field(..., description="Date/time when data was retrieved")
    fiscal_year_end: str | None = Field(
        None, description="Fiscal year end month (e.g., 'December')"
    )
    currency: str | None = Field(None, description="Reporting currency")
    metadata: dict[str, str] = Field(
        default_factory=dict, description="Additional fundamentals metadata"
    )
