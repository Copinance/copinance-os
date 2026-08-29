"""~40 (question -> expected tool set) cases covering copinance-os's own
built-in tool bundle (market data + SEC/EDGAR + macro/regime). Used by both
eval tiers in test_tool_selection_eval.py.

This is copinance-os's own dataset, scoped to tools this repo owns and
registers — apps/backend owns a separate, larger tool set (its 6 app-specific
tools plus these) and should build its own dataset importing
``run_tool_selection_eval`` rather than extending this one, since the two
repos' tool availability differs.
"""

from __future__ import annotations

from copinance_os.ai.llm.eval import ToolSelectionCase

TOOL_SELECTION_CASES: list[ToolSelectionCase] = [
    # get_market_quote
    ToolSelectionCase(
        id="quote-current-price",
        question="What is AAPL's current stock price?",
        expected_tools=frozenset({"get_market_quote"}),
    ),
    ToolSelectionCase(
        id="quote-how-is-it-trading",
        question="How is TSLA trading right now?",
        expected_tools=frozenset({"get_market_quote"}),
    ),
    ToolSelectionCase(
        id="quote-two-symbols",
        question="What are the current prices of MSFT and GOOGL?",
        expected_tools=frozenset({"get_market_quote"}),
    ),
    # get_historical_market_data
    ToolSelectionCase(
        id="historical-30-day-close",
        question="What was NVDA's closing price 30 days ago?",
        expected_tools=frozenset({"get_historical_market_data"}),
    ),
    ToolSelectionCase(
        id="historical-multi-year-chart",
        question="Show me GOOGL's daily prices from 2020-01-01 to 2024-01-01.",
        expected_tools=frozenset({"get_historical_market_data"}),
    ),
    ToolSelectionCase(
        id="historical-trailing-12-months",
        question="What has AMZN's stock done over the trailing 12 months?",
        expected_tools=frozenset({"get_historical_market_data"}),
    ),
    # search_market_instruments
    ToolSelectionCase(
        id="search-by-name",
        question="Find instruments with 'Apple' in the name.",
        expected_tools=frozenset({"search_market_instruments"}),
    ),
    ToolSelectionCase(
        id="search-ticker-lookup",
        question="What's the ticker symbol for Berkshire Hathaway?",
        expected_tools=frozenset({"search_market_instruments"}),
    ),
    # get_options_chain
    ToolSelectionCase(
        id="options-chain-single-expiry",
        question="Show me SPY's options chain for the nearest expiration.",
        expected_tools=frozenset({"get_options_chain"}),
    ),
    ToolSelectionCase(
        id="options-chain-calls-only",
        question="What call option strikes are available for QQQ this month?",
        expected_tools=frozenset({"get_options_chain"}),
    ),
    # get_options_positioning
    ToolSelectionCase(
        id="positioning-bias",
        question="What's the options positioning bias for TSLA right now?",
        expected_tools=frozenset({"get_options_positioning"}),
    ),
    ToolSelectionCase(
        id="positioning-implied-move",
        question="What's the implied move for AMZN before earnings?",
        expected_tools=frozenset({"get_options_positioning"}),
    ),
    ToolSelectionCase(
        id="positioning-gamma-regime",
        question="Is SPY in a positive or negative gamma regime?",
        expected_tools=frozenset({"get_options_positioning"}),
    ),
    # get_market_regime_indicators
    ToolSelectionCase(
        id="regime-vix-level",
        question="What is the current VIX level and volatility regime?",
        expected_tools=frozenset({"get_market_regime_indicators"}),
    ),
    ToolSelectionCase(
        id="regime-trend",
        question="Is the market currently in an uptrend or downtrend?",
        expected_tools=frozenset({"get_market_regime_indicators"}),
    ),
    # get_macro_regime_indicators
    ToolSelectionCase(
        id="macro-rates-inflation",
        question="What is the current 10-year treasury yield and CPI trend?",
        expected_tools=frozenset({"get_macro_regime_indicators"}),
    ),
    ToolSelectionCase(
        id="macro-fed-outlook",
        question="What does the macro backdrop look like for Fed policy right now?",
        expected_tools=frozenset({"get_macro_regime_indicators"}),
        acceptable_extra_tools=frozenset({"get_market_regime_indicators"}),
    ),
    # get_current_date
    ToolSelectionCase(
        id="current-date",
        question="What is today's date?",
        expected_tools=frozenset({"get_current_date"}),
    ),
    # get_sec_company_edgar_profile
    ToolSelectionCase(
        id="sec-edgar-profile",
        question="What is NVDA's CIK number and SIC classification on EDGAR?",
        expected_tools=frozenset({"get_sec_company_edgar_profile"}),
    ),
    # get_sec_company_facts_statement
    ToolSelectionCase(
        id="sec-multi-year-trend",
        question="What have Tesla's revenue and net income looked like over the past 5 years?",
        expected_tools=frozenset({"get_sec_company_facts_statement"}),
    ),
    ToolSelectionCase(
        id="sec-single-company-margins",
        question="How has Apple's gross margin trended over the last several years?",
        expected_tools=frozenset({"get_sec_company_facts_statement"}),
    ),
    # get_sec_compare_financials_metrics
    ToolSelectionCase(
        id="sec-compare-two-tickers",
        question="Compare Apple and Microsoft's revenue and operating margin.",
        expected_tools=frozenset({"get_sec_compare_financials_metrics"}),
    ),
    ToolSelectionCase(
        id="sec-compare-three-tickers",
        question="Which of AMD, NVDA, or INTC has the highest R&D spend as a percent of revenue?",
        expected_tools=frozenset({"get_sec_compare_financials_metrics"}),
    ),
    # get_sec_xbrl_statement_table
    ToolSelectionCase(
        id="sec-xbrl-segment-detail",
        question="Break down Amazon's revenue by reporting segment from its latest 10-K.",
        expected_tools=frozenset({"get_sec_xbrl_statement_table"}),
    ),
    # get_sec_13f_institutional_holdings
    ToolSelectionCase(
        id="sec-13f-institutional",
        question="Show me the latest 13F institutional holdings data for AAPL.",
        expected_tools=frozenset({"get_sec_13f_institutional_holdings"}),
    ),
    ToolSelectionCase(
        id="sec-13f-who-owns",
        question="Which institutions hold the largest positions in MSFT?",
        expected_tools=frozenset({"get_sec_13f_institutional_holdings"}),
    ),
    # get_sec_insider_form4
    ToolSelectionCase(
        id="sec-insider-form4",
        question="Have any Meta executives filed Form 4 insider transactions recently?",
        expected_tools=frozenset({"get_sec_insider_form4"}),
    ),
    ToolSelectionCase(
        id="sec-insider-selling",
        question="Has NVDA's CEO sold or bought any shares recently, per SEC filings?",
        expected_tools=frozenset({"get_sec_insider_form4"}),
    ),
    # get_sec_fund_entity
    ToolSelectionCase(
        id="sec-fund-entity-lookup",
        question="Look up the SEC fund entity details for ticker SPY.",
        expected_tools=frozenset({"get_sec_fund_entity"}),
        acceptable_extra_tools=frozenset({"find_sec_funds"}),
    ),
    # get_sec_fund_filings
    ToolSelectionCase(
        id="sec-fund-filings-list",
        question="What SEC filings has the Vanguard S&P 500 ETF submitted recently?",
        expected_tools=frozenset({"get_sec_fund_filings"}),
        acceptable_extra_tools=frozenset({"find_sec_funds"}),
    ),
    # get_sec_fund_latest_report
    ToolSelectionCase(
        id="sec-fund-latest-nport",
        question="What is the latest N-PORT report on file for ticker VOO?",
        expected_tools=frozenset({"get_sec_fund_latest_report"}),
        acceptable_extra_tools=frozenset({"find_sec_funds"}),
    ),
    # get_sec_fund_portfolio
    ToolSelectionCase(
        id="sec-fund-top-holdings",
        question="What are the top 10 holdings in ARKK right now?",
        expected_tools=frozenset({"get_sec_fund_portfolio"}),
        acceptable_extra_tools=frozenset({"find_sec_funds"}),
    ),
    ToolSelectionCase(
        id="sec-fund-portfolio-weights",
        question="What percentage of QQQ's portfolio is allocated to NVDA?",
        expected_tools=frozenset({"get_sec_fund_portfolio"}),
        acceptable_extra_tools=frozenset({"find_sec_funds"}),
    ),
    # find_sec_funds
    ToolSelectionCase(
        id="find-sec-funds-by-keyword",
        question="Search SEC fund filings for funds matching 'growth' in the name.",
        expected_tools=frozenset({"find_sec_funds"}),
    ),
    # Multi-tool composite questions
    ToolSelectionCase(
        id="composite-price-and-positioning",
        question="What is AAPL's current price, and what does the options market think about it?",
        expected_tools=frozenset({"get_market_quote", "get_options_positioning"}),
    ),
    ToolSelectionCase(
        id="composite-compare-and-history",
        question=(
            "Compare AAPL and MSFT's revenue growth, and show me AAPL's price history "
            "over the last year."
        ),
        expected_tools=frozenset(
            {"get_sec_compare_financials_metrics", "get_historical_market_data"}
        ),
    ),
    ToolSelectionCase(
        id="composite-macro-and-regime",
        question=(
            "What's the current macro backdrop (rates, inflation) and market volatility regime?"
        ),
        expected_tools=frozenset({"get_macro_regime_indicators", "get_market_regime_indicators"}),
    ),
    ToolSelectionCase(
        id="composite-chain-and-positioning",
        question="Show me SPY's options chain and its overall positioning bias.",
        expected_tools=frozenset({"get_options_chain", "get_options_positioning"}),
    ),
    ToolSelectionCase(
        id="composite-search-then-quote",
        question="Find the ticker for Alphabet, then tell me its current price.",
        expected_tools=frozenset({"search_market_instruments", "get_market_quote"}),
    ),
    ToolSelectionCase(
        id="composite-fund-holdings-and-filings",
        question="What are ARKK's top holdings, and what filings has it submitted recently?",
        expected_tools=frozenset({"get_sec_fund_portfolio", "get_sec_fund_filings"}),
        acceptable_extra_tools=frozenset({"find_sec_funds"}),
    ),
]
