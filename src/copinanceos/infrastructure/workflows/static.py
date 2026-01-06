"""Static workflow executor implementation."""

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from copinanceos.application.use_cases.fundamentals import (
    ResearchStockFundamentalsRequest,
    ResearchStockFundamentalsUseCase,
)
from copinanceos.application.use_cases.stock import GetStockRequest, GetStockUseCase
from copinanceos.domain.models.research import Research, ResearchTimeframe
from copinanceos.domain.ports.data_providers import MarketDataProvider
from copinanceos.infrastructure.workflows.base import BaseWorkflowExecutor

logger = structlog.get_logger(__name__)


class StaticWorkflowExecutor(BaseWorkflowExecutor):
    """Executor for static/predefined workflows.

    This executor performs a consistent, predefined sequence of analysis steps:
    1. Fetch stock information
    2. Get current market quote
    3. Retrieve historical price data (timeframe-dependent)
    4. Get fundamental data
    5. Calculate key metrics and trends
    6. Generate analysis summary

    The workflow adapts to the research timeframe:
    - Short-term: Focus on recent price movements and technical indicators
    - Mid-term: Focus on quarterly fundamentals and price trends
    - Long-term: Focus on annual fundamentals and long-term trends
    """

    def __init__(
        self,
        get_stock_use_case: GetStockUseCase | None = None,
        market_data_provider: MarketDataProvider | None = None,
        fundamentals_use_case: ResearchStockFundamentalsUseCase | None = None,
    ) -> None:
        """Initialize static workflow executor.

        Args:
            get_stock_use_case: Use case for getting stock information
            market_data_provider: Provider for market data (quotes, historical)
            fundamentals_use_case: Use case for researching stock fundamentals
        """
        self._get_stock_use_case = get_stock_use_case
        self._market_data_provider = market_data_provider
        self._fundamentals_use_case = fundamentals_use_case

    async def _execute_workflow(
        self, research: Research, context: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Execute a static workflow with predefined analysis steps.

        Args:
            research: The research entity to execute
            context: Execution context and parameters

        Returns:
            Results dictionary containing comprehensive analysis
        """
        symbol = research.stock_symbol.upper()
        timeframe = research.timeframe

        results: dict[str, Any] = {
            "analysis_type": "comprehensive_static",
        }

        # Step 1: Get stock information
        stock_info = await self._get_stock_info(symbol)
        results["stock_info"] = stock_info

        # Step 2: Get current market quote
        quote = await self._get_market_quote(symbol)
        results["current_quote"] = quote

        # Step 3: Get historical price data (timeframe-dependent)
        historical_data = await self._get_historical_data(symbol, timeframe)
        results["historical_data"] = historical_data

        # Step 4: Get fundamental data
        fundamentals = await self._get_fundamentals(symbol, timeframe)
        results["fundamentals"] = fundamentals

        # Step 5: Calculate key metrics and trends
        analysis = await self._calculate_analysis(
            symbol, quote, historical_data, fundamentals, timeframe
        )
        results["analysis"] = analysis

        # Step 6: Generate summary
        summary = self._generate_summary(stock_info, quote, fundamentals, analysis, timeframe)
        results["summary"] = summary

        return results

    async def _get_stock_info(self, symbol: str) -> dict[str, Any]:
        """Get stock information."""
        if not self._get_stock_use_case:
            logger.warning("GetStockUseCase not available, skipping stock info")
            return {"symbol": symbol, "note": "Stock info not available"}

        try:
            request = GetStockRequest(symbol=symbol)
            response = await self._get_stock_use_case.execute(request)

            if response.stock:
                return {
                    "symbol": response.stock.symbol,
                    "name": response.stock.name,
                    "exchange": response.stock.exchange,
                    "sector": response.stock.sector,
                    "industry": response.stock.industry,
                    "market_cap": (
                        str(response.stock.market_cap) if response.stock.market_cap else None
                    ),
                    "currency": response.stock.currency,
                }
            return {"symbol": symbol, "note": "Stock not found in repository"}
        except Exception as e:
            logger.warning("Failed to get stock info", symbol=symbol, error=str(e))
            return {"symbol": symbol, "error": str(e)}

    async def _get_market_quote(self, symbol: str) -> dict[str, Any]:
        """Get current market quote."""
        if not self._market_data_provider:
            logger.warning("MarketDataProvider not available, skipping quote")
            return {"symbol": symbol, "note": "Quote not available"}

        try:
            quote = await self._market_data_provider.get_quote(symbol)
            return {
                "symbol": quote.get("symbol", symbol),
                "current_price": str(quote.get("current_price", 0)),
                "previous_close": str(quote.get("previous_close", 0)),
                "open": str(quote.get("open", 0)),
                "high": str(quote.get("high", 0)),
                "low": str(quote.get("low", 0)),
                "volume": quote.get("volume", 0),
                "market_cap": quote.get("market_cap"),
                "currency": quote.get("currency", "USD"),
                "exchange": quote.get("exchange", ""),
                "timestamp": quote.get("timestamp"),
            }
        except Exception as e:
            logger.warning("Failed to get market quote", symbol=symbol, error=str(e))
            return {"symbol": symbol, "error": str(e)}

    async def _get_historical_data(
        self, symbol: str, timeframe: ResearchTimeframe
    ) -> dict[str, Any]:
        """Get historical price data based on timeframe."""
        if not self._market_data_provider:
            logger.warning("MarketDataProvider not available, skipping historical data")
            return {"symbol": symbol, "note": "Historical data not available"}

        try:
            # Determine date range based on timeframe
            end_date = datetime.now(UTC)
            if timeframe == ResearchTimeframe.SHORT_TERM:
                start_date = end_date - timedelta(days=30)  # 30 days
                interval = "1d"
            elif timeframe == ResearchTimeframe.MID_TERM:
                start_date = end_date - timedelta(days=180)  # 6 months
                interval = "1d"
            else:  # LONG_TERM
                start_date = end_date - timedelta(days=365 * 2)  # 2 years
                interval = "1wk"

            historical = await self._market_data_provider.get_historical_data(
                symbol, start_date, end_date, interval
            )

            if not historical:
                return {"symbol": symbol, "data_points": 0, "note": "No historical data available"}

            # Calculate price statistics
            prices = [float(d.close_price) for d in historical if d.close_price]
            volumes = [d.volume for d in historical if d.volume]

            price_stats = {}
            if prices:
                price_stats = {
                    "current_price": str(prices[-1]),
                    "period_start_price": str(prices[0]),
                    "period_high": str(max(prices)),
                    "period_low": str(min(prices)),
                    "price_change": str(prices[-1] - prices[0]),
                    "price_change_pct": (
                        str(((prices[-1] - prices[0]) / prices[0]) * 100) if prices[0] > 0 else "0"
                    ),
                }

            volume_stats = {}
            if volumes:
                volume_stats = {
                    "average_volume": str(sum(volumes) // len(volumes)),
                    "max_volume": str(max(volumes)),
                    "min_volume": str(min(volumes)),
                }

            return {
                "symbol": symbol,
                "data_points": len(historical),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "interval": interval,
                "price_statistics": price_stats,
                "volume_statistics": volume_stats,
            }
        except Exception as e:
            logger.warning("Failed to get historical data", symbol=symbol, error=str(e))
            return {"symbol": symbol, "error": str(e)}

    async def _get_fundamentals(self, symbol: str, timeframe: ResearchTimeframe) -> dict[str, Any]:
        """Get fundamental data based on timeframe."""
        if not self._fundamentals_use_case:
            logger.warning("FundamentalsUseCase not available, skipping fundamentals")
            return {"symbol": symbol, "note": "Fundamentals not available"}

        try:
            # Determine periods and period type based on timeframe
            if timeframe == ResearchTimeframe.SHORT_TERM:
                periods = 4  # Last 4 quarters
                period_type = "quarterly"
            elif timeframe == ResearchTimeframe.MID_TERM:
                periods = 8  # Last 8 quarters (2 years)
                period_type = "quarterly"
            else:  # LONG_TERM
                periods = 5  # Last 5 years
                period_type = "annual"

            request = ResearchStockFundamentalsRequest(
                symbol=symbol, periods=periods, period_type=period_type
            )
            response = await self._fundamentals_use_case.execute(request)
            fundamentals = response.fundamentals

            # Extract comprehensive fundamental data including full financial statements
            fundamentals_dict: dict[str, Any] = {
                "symbol": fundamentals.symbol,
                "company_name": fundamentals.company_name,
                "sector": fundamentals.sector,
                "industry": fundamentals.industry,
                "provider": fundamentals.provider,
                "data_as_of": fundamentals.data_as_of.isoformat(),
                "currency": fundamentals.currency,
                "fiscal_year_end": fundamentals.fiscal_year_end,
                "market_cap": str(fundamentals.market_cap) if fundamentals.market_cap else None,
                "enterprise_value": (
                    str(fundamentals.enterprise_value) if fundamentals.enterprise_value else None
                ),
                "current_price": (
                    str(fundamentals.current_price) if fundamentals.current_price else None
                ),
                "shares_outstanding": fundamentals.shares_outstanding,
                "float_shares": fundamentals.float_shares,
                "income_statements_count": len(fundamentals.income_statements),
                "balance_sheets_count": len(fundamentals.balance_sheets),
                "cash_flow_statements_count": len(fundamentals.cash_flow_statements),
                "metadata": fundamentals.metadata,
            }

            # Add ratios if available
            if fundamentals.ratios:
                ratios_dict: dict[str, Any] = {}
                for field_name, field_value in fundamentals.ratios.model_dump().items():
                    if field_value is not None:
                        # Keep metadata as dict, convert other fields to string
                        if field_name == "metadata" and isinstance(field_value, dict):
                            ratios_dict[field_name] = field_value
                        else:
                            ratios_dict[field_name] = str(field_value)
                fundamentals_dict["ratios"] = ratios_dict

            # Add most recent financial statement summaries (full details)
            if fundamentals.income_statements:
                latest_income = fundamentals.income_statements[0]
                fundamentals_dict["latest_income_statement"] = {
                    "period": latest_income.period.period_end_date.isoformat(),
                    "period_type": latest_income.period.period_type,
                    "fiscal_year": latest_income.period.fiscal_year,
                    "fiscal_quarter": latest_income.period.fiscal_quarter,
                    "total_revenue": (
                        str(latest_income.total_revenue) if latest_income.total_revenue else None
                    ),
                    "cost_of_revenue": (
                        str(latest_income.cost_of_revenue)
                        if latest_income.cost_of_revenue
                        else None
                    ),
                    "gross_profit": (
                        str(latest_income.gross_profit) if latest_income.gross_profit else None
                    ),
                    "operating_expenses": (
                        str(latest_income.operating_expenses)
                        if latest_income.operating_expenses
                        else None
                    ),
                    "operating_income": (
                        str(latest_income.operating_income)
                        if latest_income.operating_income
                        else None
                    ),
                    "interest_expense": (
                        str(latest_income.interest_expense)
                        if latest_income.interest_expense
                        else None
                    ),
                    "income_before_tax": (
                        str(latest_income.income_before_tax)
                        if latest_income.income_before_tax
                        else None
                    ),
                    "income_tax_expense": (
                        str(latest_income.income_tax_expense)
                        if latest_income.income_tax_expense
                        else None
                    ),
                    "net_income": (
                        str(latest_income.net_income) if latest_income.net_income else None
                    ),
                    "earnings_per_share": (
                        str(latest_income.earnings_per_share)
                        if latest_income.earnings_per_share
                        else None
                    ),
                    "diluted_eps": (
                        str(latest_income.diluted_eps) if latest_income.diluted_eps else None
                    ),
                    "shares_outstanding": latest_income.shares_outstanding,
                    "diluted_shares": latest_income.diluted_shares,
                    "metadata": latest_income.metadata,
                }

            if fundamentals.balance_sheets:
                latest_balance = fundamentals.balance_sheets[0]
                fundamentals_dict["latest_balance_sheet"] = {
                    "period": latest_balance.period.period_end_date.isoformat(),
                    "period_type": latest_balance.period.period_type,
                    "fiscal_year": latest_balance.period.fiscal_year,
                    "fiscal_quarter": latest_balance.period.fiscal_quarter,
                    # Assets
                    "cash_and_cash_equivalents": (
                        str(latest_balance.cash_and_cash_equivalents)
                        if latest_balance.cash_and_cash_equivalents
                        else None
                    ),
                    "short_term_investments": (
                        str(latest_balance.short_term_investments)
                        if latest_balance.short_term_investments
                        else None
                    ),
                    "accounts_receivable": (
                        str(latest_balance.accounts_receivable)
                        if latest_balance.accounts_receivable
                        else None
                    ),
                    "inventory": (
                        str(latest_balance.inventory) if latest_balance.inventory else None
                    ),
                    "current_assets": (
                        str(latest_balance.current_assets)
                        if latest_balance.current_assets
                        else None
                    ),
                    "property_plant_equipment": (
                        str(latest_balance.property_plant_equipment)
                        if latest_balance.property_plant_equipment
                        else None
                    ),
                    "long_term_investments": (
                        str(latest_balance.long_term_investments)
                        if latest_balance.long_term_investments
                        else None
                    ),
                    "total_assets": (
                        str(latest_balance.total_assets) if latest_balance.total_assets else None
                    ),
                    # Liabilities
                    "accounts_payable": (
                        str(latest_balance.accounts_payable)
                        if latest_balance.accounts_payable
                        else None
                    ),
                    "short_term_debt": (
                        str(latest_balance.short_term_debt)
                        if latest_balance.short_term_debt
                        else None
                    ),
                    "current_liabilities": (
                        str(latest_balance.current_liabilities)
                        if latest_balance.current_liabilities
                        else None
                    ),
                    "long_term_debt": (
                        str(latest_balance.long_term_debt)
                        if latest_balance.long_term_debt
                        else None
                    ),
                    "total_liabilities": (
                        str(latest_balance.total_liabilities)
                        if latest_balance.total_liabilities
                        else None
                    ),
                    # Equity
                    "common_stock": (
                        str(latest_balance.common_stock) if latest_balance.common_stock else None
                    ),
                    "retained_earnings": (
                        str(latest_balance.retained_earnings)
                        if latest_balance.retained_earnings
                        else None
                    ),
                    "total_equity": (
                        str(latest_balance.total_equity) if latest_balance.total_equity else None
                    ),
                    "total_liabilities_and_equity": (
                        str(latest_balance.total_liabilities_and_equity)
                        if latest_balance.total_liabilities_and_equity
                        else None
                    ),
                    "metadata": latest_balance.metadata,
                }

            if fundamentals.cash_flow_statements:
                latest_cashflow = fundamentals.cash_flow_statements[0]
                fundamentals_dict["latest_cash_flow_statement"] = {
                    "period": latest_cashflow.period.period_end_date.isoformat(),
                    "period_type": latest_cashflow.period.period_type,
                    "fiscal_year": latest_cashflow.period.fiscal_year,
                    "fiscal_quarter": latest_cashflow.period.fiscal_quarter,
                    # Operating Activities
                    "net_income": (
                        str(latest_cashflow.net_income) if latest_cashflow.net_income else None
                    ),
                    "depreciation_amortization": (
                        str(latest_cashflow.depreciation_amortization)
                        if latest_cashflow.depreciation_amortization
                        else None
                    ),
                    "stock_based_compensation": (
                        str(latest_cashflow.stock_based_compensation)
                        if latest_cashflow.stock_based_compensation
                        else None
                    ),
                    "changes_in_working_capital": (
                        str(latest_cashflow.changes_in_working_capital)
                        if latest_cashflow.changes_in_working_capital
                        else None
                    ),
                    "operating_cash_flow": (
                        str(latest_cashflow.operating_cash_flow)
                        if latest_cashflow.operating_cash_flow
                        else None
                    ),
                    # Investing Activities
                    "capital_expenditures": (
                        str(latest_cashflow.capital_expenditures)
                        if latest_cashflow.capital_expenditures
                        else None
                    ),
                    "investments": (
                        str(latest_cashflow.investments) if latest_cashflow.investments else None
                    ),
                    "investing_cash_flow": (
                        str(latest_cashflow.investing_cash_flow)
                        if latest_cashflow.investing_cash_flow
                        else None
                    ),
                    # Financing Activities
                    "debt_issued": (
                        str(latest_cashflow.debt_issued) if latest_cashflow.debt_issued else None
                    ),
                    "debt_repaid": (
                        str(latest_cashflow.debt_repaid) if latest_cashflow.debt_repaid else None
                    ),
                    "dividends_paid": (
                        str(latest_cashflow.dividends_paid)
                        if latest_cashflow.dividends_paid
                        else None
                    ),
                    "share_repurchases": (
                        str(latest_cashflow.share_repurchases)
                        if latest_cashflow.share_repurchases
                        else None
                    ),
                    "share_issuance": (
                        str(latest_cashflow.share_issuance)
                        if latest_cashflow.share_issuance
                        else None
                    ),
                    "financing_cash_flow": (
                        str(latest_cashflow.financing_cash_flow)
                        if latest_cashflow.financing_cash_flow
                        else None
                    ),
                    # Net Change
                    "net_change_in_cash": (
                        str(latest_cashflow.net_change_in_cash)
                        if latest_cashflow.net_change_in_cash
                        else None
                    ),
                    "free_cash_flow": (
                        str(latest_cashflow.free_cash_flow)
                        if latest_cashflow.free_cash_flow
                        else None
                    ),
                    "metadata": latest_cashflow.metadata,
                }

            return fundamentals_dict
        except Exception as e:
            logger.warning("Failed to get fundamentals", symbol=symbol, error=str(e))
            return {"symbol": symbol, "error": str(e)}

    async def _calculate_analysis(
        self,
        symbol: str,
        quote: dict[str, Any],
        historical_data: dict[str, Any],
        fundamentals: dict[str, Any],
        timeframe: ResearchTimeframe,
    ) -> dict[str, Any]:
        """Calculate key metrics and trends."""
        analysis: dict[str, Any] = {
            "symbol": symbol,
            "timeframe": timeframe.value,
            "metrics": {},
            "trends": {},
            "assessments": {},
        }

        # Price trend analysis
        if historical_data.get("price_statistics"):
            price_stats = historical_data["price_statistics"]
            price_change_pct = float(price_stats.get("price_change_pct", 0))
            analysis["trends"]["price_trend"] = {
                "direction": "up" if price_change_pct > 0 else "down",
                "magnitude": abs(price_change_pct),
                "change_pct": str(price_change_pct),
            }

        # Valuation metrics from fundamentals
        if fundamentals.get("ratios"):
            ratios = fundamentals["ratios"]
            analysis["metrics"]["valuation"] = {
                "pe_ratio": ratios.get("price_to_earnings"),
                "pb_ratio": ratios.get("price_to_book"),
                "ps_ratio": ratios.get("price_to_sales"),
                "ev_ebitda": ratios.get("enterprise_value_to_ebitda"),
            }

        # Profitability metrics
        if fundamentals.get("ratios"):
            ratios = fundamentals["ratios"]
            analysis["metrics"]["profitability"] = {
                "gross_margin": ratios.get("gross_margin"),
                "operating_margin": ratios.get("operating_margin"),
                "net_margin": ratios.get("net_margin"),
                "roe": ratios.get("return_on_equity"),
                "roa": ratios.get("return_on_assets"),
            }

        # Financial health metrics
        if fundamentals.get("ratios"):
            ratios = fundamentals["ratios"]
            analysis["metrics"]["financial_health"] = {
                "current_ratio": ratios.get("current_ratio"),
                "quick_ratio": ratios.get("quick_ratio"),
                "debt_to_equity": ratios.get("debt_to_equity"),
                "interest_coverage": ratios.get("interest_coverage"),
            }

        # Growth metrics
        if fundamentals.get("ratios"):
            ratios = fundamentals["ratios"]
            analysis["metrics"]["growth"] = {
                "revenue_growth": ratios.get("revenue_growth"),
                "earnings_growth": ratios.get("earnings_growth"),
                "fcf_growth": ratios.get("free_cash_flow_growth"),
            }

        # Basic assessments
        assessments = []
        if quote.get("current_price"):
            current_price = float(quote["current_price"])
            if historical_data.get("price_statistics"):
                period_high = float(historical_data["price_statistics"].get("period_high", 0))
                period_low = float(historical_data["price_statistics"].get("period_low", 0))
                if period_high > 0:
                    price_position = (current_price - period_low) / (period_high - period_low)
                    if price_position > 0.8:
                        assessments.append("Trading near period high")
                    elif price_position < 0.2:
                        assessments.append("Trading near period low")

        if fundamentals.get("ratios", {}).get("current_ratio"):
            current_ratio = float(fundamentals["ratios"]["current_ratio"])
            if current_ratio < 1.0:
                assessments.append("Current ratio below 1.0 - potential liquidity concern")
            elif current_ratio > 2.0:
                assessments.append("Strong current ratio - good liquidity position")

        analysis["assessments"] = assessments

        return analysis

    def _generate_summary(
        self,
        stock_info: dict[str, Any],
        quote: dict[str, Any],
        fundamentals: dict[str, Any],
        analysis: dict[str, Any],
        timeframe: ResearchTimeframe,
    ) -> dict[str, Any]:
        """Generate analysis summary."""
        summary_parts = []

        # Company overview
        if stock_info.get("name"):
            summary_parts.append(f"Company: {stock_info['name']}")
        if stock_info.get("sector"):
            summary_parts.append(f"Sector: {stock_info['sector']}")

        # Current price
        if quote.get("current_price"):
            price_change = ""
            if quote.get("previous_close"):
                prev_close = float(quote["previous_close"])
                curr_price = float(quote["current_price"])
                change = curr_price - prev_close
                change_pct = (change / prev_close * 100) if prev_close > 0 else 0
                price_change = f" ({change:+.2f}, {change_pct:+.2f}%)"
            summary_parts.append(f"Current Price: {quote['current_price']}{price_change}")

        # Price trend
        if analysis.get("trends", {}).get("price_trend"):
            trend = analysis["trends"]["price_trend"]
            direction = "up" if trend["direction"] == "up" else "down"
            summary_parts.append(
                f"Price Trend ({timeframe.value}): {direction} {trend['magnitude']:.2f}%"
            )

        # Key metrics
        if analysis.get("metrics", {}).get("valuation", {}).get("pe_ratio"):
            pe = analysis["metrics"]["valuation"]["pe_ratio"]
            summary_parts.append(f"P/E Ratio: {pe}")

        if analysis.get("metrics", {}).get("profitability", {}).get("roe"):
            roe = analysis["metrics"]["profitability"]["roe"]
            summary_parts.append(f"ROE: {roe}%")

        # Assessments
        if analysis.get("assessments"):
            summary_parts.append("Key Observations:")
            for assessment in analysis["assessments"]:
                summary_parts.append(f"  - {assessment}")

        # Analysis Methodology
        summary_parts.append("")
        summary_parts.append("Analysis Methodology:")
        summary_parts.append(
            "  - Price Trends: (current_price - period_start_price) / period_start_price * 100"
        )
        summary_parts.append("  - Valuation Metrics:")
        summary_parts.append("    • P/E Ratio: current_price / earnings_per_share")
        summary_parts.append("    • P/B Ratio: current_price / (total_equity / shares_outstanding)")
        summary_parts.append(
            "    • P/S Ratio: current_price / (total_revenue / shares_outstanding)"
        )
        summary_parts.append(
            "    • EV/EBITDA: enterprise_value / (operating_income + depreciation)"
        )
        summary_parts.append("  - Profitability:")
        summary_parts.append("    • Gross Margin: (gross_profit / total_revenue) * 100")
        summary_parts.append("    • Operating Margin: (operating_income / total_revenue) * 100")
        summary_parts.append("    • Net Margin: (net_income / total_revenue) * 100")
        summary_parts.append("    • ROE: (net_income / total_equity) * 100")
        summary_parts.append("    • ROA: (net_income / total_assets) * 100")
        summary_parts.append("  - Financial Health:")
        summary_parts.append("    • Current Ratio: current_assets / current_liabilities")
        summary_parts.append("    • Quick Ratio: (cash + receivables) / current_liabilities")
        summary_parts.append(
            "    • Debt to Equity: (short_term_debt + long_term_debt) / total_equity"
        )
        summary_parts.append("    • Interest Coverage: operating_income / interest_expense")
        summary_parts.append("  - Growth Metrics:")
        summary_parts.append(
            "    • Revenue Growth: ((current_revenue - previous_revenue) / previous_revenue) * 100"
        )
        summary_parts.append(
            "    • Earnings Growth: ((current_earnings - previous_earnings) / abs(previous_earnings)) * 100"
        )
        summary_parts.append(
            "    • FCF Growth: ((current_fcf - previous_fcf) / abs(previous_fcf)) * 100"
        )
        summary_parts.append("  - Assessments:")
        summary_parts.append(
            "    • Price Position: (current_price - period_low) / (period_high - period_low)"
        )
        summary_parts.append("    • Liquidity: Current Ratio < 1.0 (concern), > 2.0 (strong)")

        return {
            "text": "\n".join(summary_parts),
            "timeframe": timeframe.value,
            "analysis_date": datetime.now(UTC).isoformat(),
        }

    async def validate(self, research: Research) -> bool:
        """Validate if this executor can handle the given research.

        Supports "stock" workflow type, which includes comprehensive
        fundamentals data along with market data and analysis.
        """
        return research.workflow_type == "stock"

    def get_workflow_type(self) -> str:
        """Get the workflow type identifier."""
        return "stock"
