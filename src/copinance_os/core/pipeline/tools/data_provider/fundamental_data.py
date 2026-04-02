"""Fundamental data provider tools."""

from typing import Any

import structlog

from copinance_os.core.pipeline.tools.data_provider.base import BaseDataProviderTool
from copinance_os.core.pipeline.tools.data_provider.provider_selector import (
    MultiProviderSelector,
    ProviderSelector,
)
from copinance_os.data.cache import CacheManager
from copinance_os.domain.exceptions import ConfigurationError
from copinance_os.domain.models.tool_results import ToolResult
from copinance_os.domain.ports.data_providers import FundamentalDataProvider
from copinance_os.domain.ports.tools import ToolSchema

logger = structlog.get_logger(__name__)


class BaseSecEdgarExtendedFundamentalTool(BaseDataProviderTool[FundamentalDataProvider]):
    """SEC/EDGAR tools that invoke optional methods on ``EdgarToolsFundamentalProvider``.

    Uses the same provider routing as ``get_sec_filings`` (``sec_filings`` capability).
    """

    def __init__(
        self,
        provider: (
            FundamentalDataProvider
            | ProviderSelector[FundamentalDataProvider]
            | MultiProviderSelector[FundamentalDataProvider]
        ),
        cache_manager: CacheManager | None = None,
        use_cache: bool = True,
    ) -> None:
        self._provider_or_selector = provider
        if isinstance(provider, (ProviderSelector, MultiProviderSelector)):
            if isinstance(provider, MultiProviderSelector):
                selected_provider = provider.get_provider_for_capability("sec_filings")
                if selected_provider is None:
                    selected_provider = provider.get_default_provider()
            else:
                selected_provider = provider.get_provider(tool_name="get_sec_filings")

            if selected_provider is None:
                raise ConfigurationError(
                    "No provider available for SEC/EDGAR extended tools — "
                    "configure an EDGAR provider (e.g. COPINANCEOS_EDGAR_IDENTITY)"
                )
            super().__init__(selected_provider, cache_manager=cache_manager, use_cache=use_cache)
        else:
            super().__init__(provider, cache_manager=cache_manager, use_cache=use_cache)

    def _provider_for_sec_run(self) -> FundamentalDataProvider:
        po = self._provider_or_selector
        if isinstance(po, MultiProviderSelector):
            sec_p = po.get_provider_for_capability("sec_filings")
            if sec_p is not None:
                return sec_p
            d = po.get_default_provider()
            if d is not None:
                return d
        elif isinstance(po, ProviderSelector):
            p = po.get_provider(tool_name="get_sec_filings")
            if p is not None:
                return p
        return self._provider


class FundamentalDataGetFundamentalsTool(BaseDataProviderTool[FundamentalDataProvider]):
    """Tool for getting detailed equity fundamentals."""

    def __init__(
        self,
        provider: FundamentalDataProvider,
        cache_manager: CacheManager | None = None,
        use_cache: bool = True,
    ) -> None:
        """Initialize tool with fundamental data provider.

        Args:
            provider: Fundamental data provider instance
            cache_manager: Optional cache manager for caching tool results
            use_cache: Whether to use caching (default: True if cache_manager is provided)
        """
        super().__init__(provider, cache_manager=cache_manager, use_cache=use_cache)

    def get_name(self) -> str:
        """Get tool name."""
        return "get_equity_fundamentals"

    def get_description(self) -> str:
        """Get tool description."""
        return "Get comprehensive fundamental data for an equity including financial statements, ratios, and metrics."

    def get_schema(self) -> ToolSchema:
        """Get tool schema."""
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Equity ticker symbol (e.g., 'AAPL', 'MSFT')",
                    },
                    "periods": {
                        "type": "integer",
                        "description": "Number of periods to retrieve (e.g., 5 for 5 years)",
                        "default": 5,
                    },
                    "period_type": {
                        "type": "string",
                        "description": "Period type",
                        "enum": ["annual", "quarterly"],
                        "default": "annual",
                    },
                },
                "required": ["symbol"],
            },
            returns={
                "type": "object",
                "description": "Comprehensive fundamental data including financial statements and ratios",
            },
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        """Execute tool to get fundamentals."""
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        """Execute tool implementation."""
        try:
            validated = self.validate_parameters(**kwargs)
            symbol = validated["symbol"]
            periods = validated.get("periods", 5)
            period_type = validated.get("period_type", "annual")

            fundamentals = await self._provider.get_detailed_fundamentals(
                symbol=symbol,
                periods=periods,
                period_type=period_type,
            )

            # Convert to serializable format
            data = self._serialize_data(fundamentals)

            return self._create_success_result(
                data=data,
                metadata={
                    "symbol": symbol,
                    "periods": periods,
                    "period_type": period_type,
                },
            )
        except Exception as e:
            logger.error("Failed to get fundamentals", error=str(e), symbol=kwargs.get("symbol"))
            return self._create_error_result(
                error=e,
                metadata={"symbol": kwargs.get("symbol")},
            )


class FundamentalDataGetFinancialStatementsTool(BaseDataProviderTool[FundamentalDataProvider]):
    """Tool for getting financial statements."""

    def __init__(
        self,
        provider: FundamentalDataProvider,
        cache_manager: CacheManager | None = None,
        use_cache: bool = True,
    ) -> None:
        """Initialize tool with fundamental data provider.

        Args:
            provider: Fundamental data provider instance
            cache_manager: Optional cache manager for caching tool results
            use_cache: Whether to use caching (default: True if cache_manager is provided)
        """
        super().__init__(provider, cache_manager=cache_manager, use_cache=use_cache)

    def get_name(self) -> str:
        """Get tool name."""
        return "get_financial_statements"

    def get_description(self) -> str:
        """Get tool description."""
        return (
            "SEC EDGAR — **Financials API**: standardized income / balance / cash-flow grids for **one** ticker "
            "(recent filing bundle). For **long multi-year history** on one issuer prefer "
            "**get_sec_company_facts_statement**. For **comparing headline metrics across tickers** prefer "
            "**get_sec_compare_financials_metrics**. For **segments or dimensional rows** prefer "
            "**get_sec_xbrl_statement_table** — do not use **get_sec_filings** for statement numbers."
        )

    def get_schema(self) -> ToolSchema:
        """Get tool schema."""
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Equity ticker symbol (e.g., 'AAPL', 'MSFT')",
                    },
                    "statement_type": {
                        "type": "string",
                        "description": "Type of financial statement",
                        "enum": ["income_statement", "balance_sheet", "cash_flow"],
                    },
                    "period": {
                        "type": "string",
                        "description": "Period type",
                        "enum": ["annual", "quarterly"],
                        "default": "annual",
                    },
                },
                "required": ["symbol", "statement_type"],
            },
            returns={
                "type": "object",
                "description": "Financial statement data",
            },
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        """Execute tool to get financial statements."""
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        """Execute tool implementation."""
        try:
            validated = self.validate_parameters(**kwargs)
            symbol = validated["symbol"]
            statement_type = validated["statement_type"]
            period = validated.get("period", "annual")

            statements = await self._provider.get_financial_statements(
                symbol=symbol,
                statement_type=statement_type,
                period=period,
            )

            return self._create_success_result(
                data=statements,
                metadata={
                    "symbol": symbol,
                    "statement_type": statement_type,
                    "period": period,
                },
            )
        except Exception as e:
            logger.error(
                "Failed to get financial statements",
                error=str(e),
                symbol=kwargs.get("symbol"),
            )
            return self._create_error_result(
                error=e,
                metadata={"symbol": kwargs.get("symbol")},
            )


class FundamentalDataGetSECFilingsTool(BaseDataProviderTool[FundamentalDataProvider]):
    """Tool for getting SEC filings.

    This tool supports provider selection, allowing a dedicated provider for SEC filings
    while other tools use the default provider.
    """

    def __init__(
        self,
        provider: (
            FundamentalDataProvider
            | ProviderSelector[FundamentalDataProvider]
            | MultiProviderSelector[FundamentalDataProvider]
        ),
        cache_manager: CacheManager | None = None,
        use_cache: bool = True,
    ) -> None:
        """Initialize tool with fundamental data provider or provider selector.

        Args:
            provider: Fundamental data provider instance, ProviderSelector, or MultiProviderSelector.
                     If MultiProviderSelector, will attempt to use a provider with 'sec_filings' capability.
            cache_manager: Optional cache manager for caching tool results
            use_cache: Whether to use caching (default: True if cache_manager is provided)
        """
        # Store the original provider/selector for dynamic selection
        self._provider_or_selector = provider

        # For compatibility with BaseDataProviderTool, we need a provider instance
        # We'll select the appropriate provider during execution
        if isinstance(provider, (ProviderSelector, MultiProviderSelector)):
            # Get the best provider for SEC filings
            if isinstance(provider, MultiProviderSelector):
                selected_provider = provider.get_provider_for_capability("sec_filings")
                if selected_provider is None:
                    selected_provider = provider.get_default_provider()
            else:
                selected_provider = provider.get_provider(tool_name="get_sec_filings")

            if selected_provider is None:
                raise ConfigurationError(
                    "No provider available for SEC filings tool — configure an EDGAR provider (e.g. COPINANCEOS_EDGAR_IDENTITY)"
                )
            super().__init__(selected_provider, cache_manager=cache_manager, use_cache=use_cache)
        else:
            super().__init__(provider, cache_manager=cache_manager, use_cache=use_cache)

    def get_name(self) -> str:
        """Get tool name."""
        return "get_sec_filings"

    def get_description(self) -> str:
        """Get tool description."""
        return (
            "**Filing index only** — list SEC EDGAR filings (10-K, 10-Q, 8-K, Form 4, 13F, etc.): dates, form, "
            "accession number, CIK, URL. "
            "Do **not** use this for revenue, EPS, ratios, or statement lines — use **get_sec_company_facts_statement**, "
            "**get_financial_statements**, or **get_sec_compare_financials_metrics** instead. "
            "Use **get_sec_filing_content** only after you have CIK + accession and need raw HTML/text."
        )

    def get_schema(self) -> ToolSchema:
        """Get tool schema."""
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Equity ticker symbol (e.g., 'AAPL', 'MSFT')",
                    },
                    "filing_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of filing types (e.g., ['10-K', '10-Q', '8-K'])",
                        "default": ["10-K", "10-Q"],
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of filings to return",
                        "default": 10,
                    },
                },
                "required": ["symbol"],
            },
            returns={
                "type": "array",
                "description": "List of SEC filings with metadata",
            },
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        """Execute tool to get SEC filings.

        Selects the appropriate provider if a provider selector is configured.
        """
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        """Execute tool implementation."""
        try:
            validated = self.validate_parameters(**kwargs)
            symbol = validated["symbol"]
            filing_types = validated.get("filing_types", ["10-K", "10-Q"])
            limit = validated.get("limit", 10)

            # Select provider if using a selector
            provider = self._provider
            if isinstance(self._provider_or_selector, MultiProviderSelector):
                # Try to get provider with sec_filings capability
                sec_provider = self._provider_or_selector.get_provider_for_capability("sec_filings")
                if sec_provider:
                    provider = sec_provider
                    logger.debug(
                        "Using provider with sec_filings capability",
                        provider=provider.get_provider_name(),
                        symbol=symbol,
                    )
                else:
                    # Fall back to default provider
                    default_provider = self._provider_or_selector.get_default_provider()
                    if default_provider:
                        provider = default_provider
            elif isinstance(self._provider_or_selector, ProviderSelector):
                provider = self._provider_or_selector.get_provider(
                    tool_name=self.get_name(), params=validated
                )

            filings = await provider.get_sec_filings(
                symbol=symbol,
                filing_types=filing_types,
                limit=limit,
            )

            # Add helpful context when no filings found
            metadata: dict[str, Any] = {
                "symbol": symbol,
                "filing_types": filing_types,
                "limit": limit,
                "filings_count": len(filings),
                "provider": provider.get_provider_name(),
            }
            if len(filings) == 0:
                # Add suggestion for empty results
                metadata["suggestion"] = (
                    "No filings found. Consider trying other filing types "
                    "(e.g., 10-Q, 8-K, S-1) or verifying the symbol is correct."
                )
                # Allow retry with different filing types
                metadata["allow_retry"] = True

            return self._create_success_result(
                data=filings,
                metadata=metadata,
            )
        except Exception as e:
            logger.error("Failed to get SEC filings", error=str(e), symbol=kwargs.get("symbol"))
            return self._create_error_result(
                error=e,
                metadata={"symbol": kwargs.get("symbol")},
            )


class FundamentalDataGetSECFilingContentTool(BaseDataProviderTool[FundamentalDataProvider]):
    """Tool for downloading SEC filing content (10-K, 10-Q reports, etc.).

    This tool downloads the actual content of SEC filings, allowing the LLM to
    read and analyze the full text of reports.
    """

    def __init__(
        self,
        provider: (
            FundamentalDataProvider
            | ProviderSelector[FundamentalDataProvider]
            | MultiProviderSelector[FundamentalDataProvider]
        ),
        cache_manager: CacheManager | None = None,
        use_cache: bool = True,
    ) -> None:
        """Initialize tool with fundamental data provider or provider selector.

        Args:
            provider: Fundamental data provider instance, ProviderSelector, or MultiProviderSelector.
                     If MultiProviderSelector, will attempt to use a provider with 'sec_filings' capability.
            cache_manager: Optional cache manager for caching tool results
            use_cache: Whether to use caching (default: True if cache_manager is provided)
        """
        # Store the original provider/selector for dynamic selection
        self._provider_or_selector = provider

        # For compatibility with BaseDataProviderTool, we need a provider instance
        if isinstance(provider, (ProviderSelector, MultiProviderSelector)):
            # Get the best provider for SEC filings
            if isinstance(provider, MultiProviderSelector):
                selected_provider = provider.get_provider_for_capability("sec_filings")
                if selected_provider is None:
                    selected_provider = provider.get_default_provider()
            else:
                selected_provider = provider.get_provider(tool_name="get_sec_filing_content")

            if selected_provider is None:
                raise ConfigurationError(
                    "No provider available for SEC filing content tool — configure an EDGAR provider (e.g. COPINANCEOS_EDGAR_IDENTITY)"
                )
            super().__init__(selected_provider, cache_manager=cache_manager, use_cache=use_cache)
        else:
            super().__init__(provider, cache_manager=cache_manager, use_cache=use_cache)

    def get_name(self) -> str:
        """Get tool name."""
        return "get_sec_filing_content"

    def get_description(self) -> str:
        """Get tool description."""
        return (
            "Download full SEC filing text/HTML by CIK + accession (10-K, 10-Q, etc.). "
            "Heavy payload — only when narrative or sections not available via facts/financials/XBRL tools. "
            "Get accession from **get_sec_filings** or from the user; do not call this for simple numeric metrics."
        )

    def get_schema(self) -> ToolSchema:
        """Get tool schema."""
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "cik": {
                        "type": "string",
                        "description": "Central Index Key (10 digits, zero-padded, e.g., '0000320193')",
                    },
                    "accession_number": {
                        "type": "string",
                        "description": "SEC accession number (e.g., '0000320193-23-000077')",
                    },
                    "document_type": {
                        "type": "string",
                        "enum": ["full", "html", "index"],
                        "description": "Type of document to retrieve: 'full' (full text, default), 'html' (HTML version), 'index' (filing index)",
                        "default": "full",
                    },
                },
                "required": ["cik", "accession_number"],
            },
            returns={
                "type": "object",
                "description": "Filing content with metadata including the full text content",
            },
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        """Execute tool to download SEC filing content.

        Selects the appropriate provider if a provider selector is configured.
        """
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        """Execute tool implementation."""
        try:
            validated = self.validate_parameters(**kwargs)
            cik = validated["cik"]
            accession_number = validated["accession_number"]
            document_type = validated.get("document_type", "full")

            # Select provider if using a selector
            provider = self._provider
            if isinstance(self._provider_or_selector, MultiProviderSelector):
                # Try to get provider with sec_filings capability
                sec_provider = self._provider_or_selector.get_provider_for_capability("sec_filings")
                if sec_provider:
                    provider = sec_provider
                    logger.debug(
                        "Using provider with sec_filings capability",
                        provider=provider.get_provider_name(),
                        cik=cik,
                    )
                else:
                    # Fall back to default provider
                    default_provider = self._provider_or_selector.get_default_provider()
                    if default_provider:
                        provider = default_provider
            elif isinstance(self._provider_or_selector, ProviderSelector):
                provider = self._provider_or_selector.get_provider(
                    tool_name=self.get_name(), params=validated
                )

            # Check if provider supports get_sec_filing_content
            if not hasattr(provider, "get_sec_filing_content"):
                return self._create_error_result(
                    error=ValueError(
                        f"Provider {provider.get_provider_name()} does not support downloading SEC filing content. "
                        "Use a fundamental data provider that implements get_sec_filing_content."
                    ),
                    metadata={"cik": cik, "accession_number": accession_number},
                )

            # Download filing content
            result = await provider.get_sec_filing_content(
                cik=cik,
                accession_number=accession_number,
                document_type=document_type,
            )

            if "error" in result:
                return self._create_error_result(
                    error=ValueError(result["error"]),
                    metadata={"cik": cik, "accession_number": accession_number},
                )

            return self._create_success_result(
                data=result,
                metadata={
                    "cik": cik,
                    "accession_number": accession_number,
                    "document_type": document_type,
                    "provider": provider.get_provider_name(),
                },
            )
        except Exception as e:
            logger.error(
                "Failed to get SEC filing content",
                error=str(e),
                cik=kwargs.get("cik"),
                accession_number=kwargs.get("accession_number"),
            )
            return self._create_error_result(
                error=e,
                metadata={
                    "cik": kwargs.get("cik"),
                    "accession_number": kwargs.get("accession_number"),
                },
            )


class FundamentalDataGetSECCompanyFactsStatementTool(BaseSecEdgarExtendedFundamentalTool):
    """Single-company multi-period facts from SEC Entity Facts (long history trends)."""

    def get_name(self) -> str:
        return "get_sec_company_facts_statement"

    def get_description(self) -> str:
        return (
            "SEC EDGAR — **Company Facts / Entity Facts** API: multi-period income, balance sheet, or cash flow "
            "for **one** ticker (e.g. revenue over 5+ years). Faster for long history than iterating filings. "
            "Use **get_sec_compare_financials_metrics** to compare metrics across tickers. "
            "Use **get_sec_xbrl_statement_table** only for segment/dimensional breakdowns."
        )

    def get_schema(self) -> ToolSchema:
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "US equity ticker or CIK (e.g. 'AAPL')",
                    },
                    "statement_kind": {
                        "type": "string",
                        "description": "Which statement to return",
                        "enum": ["income_statement", "balance_sheet", "cash_flow"],
                        "default": "income_statement",
                    },
                    "periods": {
                        "type": "integer",
                        "description": "Number of fiscal periods (1–12), e.g. 5 for five years annual",
                        "default": 5,
                    },
                    "period": {
                        "type": "string",
                        "enum": ["annual", "quarterly"],
                        "description": "Annual or quarterly facts",
                        "default": "annual",
                    },
                    "line_label": {
                        "type": "string",
                        "description": "Optional: filter to one line by label or XBRL concept (e.g. 'Revenues'). "
                        "Omit to return the full statement tree (may be large).",
                        "default": "",
                    },
                },
                "required": ["symbol"],
            },
            returns={
                "type": "object",
                "description": "Company Facts statement JSON (items or single line)",
            },
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        try:
            validated = self.validate_parameters(**kwargs)
            symbol = validated["symbol"]
            statement_kind = validated.get("statement_kind", "income_statement")
            periods = validated.get("periods", 5)
            period = validated.get("period", "annual")
            line_label = validated.get("line_label") or None
            if isinstance(line_label, str) and not line_label.strip():
                line_label = None

            provider = self._provider_for_sec_run()
            if not hasattr(provider, "get_sec_company_facts_statement"):
                return self._create_error_result(
                    error=RuntimeError(
                        "This deployment has no EDGAR Company Facts support. "
                        "Configure EdgarToolsFundamentalProvider (sec_filings_provider)."
                    ),
                    metadata={"symbol": symbol},
                )

            data = await provider.get_sec_company_facts_statement(
                symbol=symbol,
                statement_kind=statement_kind,
                periods=periods,
                period=period,
                line_label=line_label,
            )
            if "error" in data:
                return self._create_error_result(
                    error=ValueError(str(data.get("error"))),
                    metadata={"symbol": symbol},
                )
            return self._create_success_result(
                data=data,
                metadata={"symbol": symbol, "statement_kind": statement_kind},
            )
        except Exception as e:
            logger.error(
                "get_sec_company_facts_statement failed", error=str(e), symbol=kwargs.get("symbol")
            )
            return self._create_error_result(error=e, metadata={"symbol": kwargs.get("symbol")})


class FundamentalDataGetSECCompareFinancialsTool(BaseSecEdgarExtendedFundamentalTool):
    """Cross-company standardized metrics via Financials API (get_financials)."""

    def get_name(self) -> str:
        return "get_sec_compare_financials_metrics"

    def get_description(self) -> str:
        return (
            "SEC EDGAR — **Financials API** (`get_financials()`): compare **standardized** metrics across "
            "multiple tickers (e.g. Apple vs Microsoft revenue). Not for segment detail — use "
            "**get_sec_xbrl_statement_table** for dimensional/segment data."
        )

    def get_schema(self) -> ToolSchema:
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": 'List of tickers to compare (max 8), e.g. ["AAPL","MSFT"]',
                    },
                    "metrics": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "revenue",
                                "net_income",
                                "operating_income",
                                "total_assets",
                                "total_liabilities",
                                "stockholders_equity",
                                "operating_cash_flow",
                                "free_cash_flow",
                                "current_assets",
                                "current_liabilities",
                            ],
                        },
                        "description": "Standardized metrics to compare across symbols",
                        "default": ["revenue", "net_income"],
                    },
                    "period_offsets": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "0=latest period in bundle, 1=prior, etc. (max 5 offsets)",
                        "default": [0, 1, 2],
                    },
                },
                "required": ["symbols"],
            },
            returns={"type": "object", "description": "Per-symbol metric columns for comparison"},
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        try:
            validated = self.validate_parameters(**kwargs)
            symbols = validated["symbols"]
            metrics = validated.get("metrics", ["revenue", "net_income"])
            period_offsets = validated.get("period_offsets", [0, 1, 2])

            provider = self._provider_for_sec_run()
            if not hasattr(provider, "get_sec_compare_financials_metrics"):
                return self._create_error_result(
                    error=RuntimeError(
                        "This deployment has no EDGAR compare-financials support. "
                        "Configure EdgarToolsFundamentalProvider (sec_filings_provider)."
                    ),
                    metadata={"symbols": symbols},
                )

            data = await provider.get_sec_compare_financials_metrics(
                symbols=symbols,
                metrics=metrics,
                period_offsets=period_offsets,
            )
            return self._create_success_result(data=data, metadata={"symbols": symbols})
        except Exception as e:
            logger.error("get_sec_compare_financials_metrics failed", error=str(e))
            return self._create_error_result(error=e, metadata={})


class FundamentalDataGetSECXbrlStatementTableTool(BaseSecEdgarExtendedFundamentalTool):
    """XBRL statement table from latest filing — segments / dimensions."""

    def get_name(self) -> str:
        return "get_sec_xbrl_statement_table"

    def get_description(self) -> str:
        return (
            "SEC EDGAR — **XBRL** from the latest filing of a given form: income, balance sheet, or cash flow "
            "as a table. Use **view 'detailed'** when you need dimensional (e.g. segment) rows. Slower than "
            "Company Facts or Financials; use only when segments or filing-native presentation is required."
        )

    def get_schema(self) -> ToolSchema:
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "symbol": {"type": "string", "description": "US equity ticker (e.g. 'AAPL')"},
                    "form": {
                        "type": "string",
                        "description": "Filing form to take the latest of",
                        "default": "10-K",
                    },
                    "statement": {
                        "type": "string",
                        "enum": ["income", "balance_sheet", "cash_flow"],
                        "description": "Which primary statement to extract",
                        "default": "income",
                    },
                    "view": {
                        "type": "string",
                        "enum": ["standard", "detailed", "summary"],
                        "description": "'detailed' includes dimensional/segment rows when present",
                        "default": "detailed",
                    },
                    "max_rows": {
                        "type": "integer",
                        "description": "Cap rows returned (tool may truncate for LLM context)",
                        "default": 300,
                    },
                },
                "required": ["symbol"],
            },
            returns={"type": "object", "description": "Table columns and row records"},
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        try:
            validated = self.validate_parameters(**kwargs)
            symbol = validated["symbol"]
            form = validated.get("form", "10-K")
            statement = validated.get("statement", "income")
            view = validated.get("view", "detailed")
            max_rows = validated.get("max_rows", 300)

            provider = self._provider_for_sec_run()
            if not hasattr(provider, "get_sec_xbrl_statement_table"):
                return self._create_error_result(
                    error=RuntimeError(
                        "This deployment has no EDGAR XBRL table support. "
                        "Configure EdgarToolsFundamentalProvider (sec_filings_provider)."
                    ),
                    metadata={"symbol": symbol},
                )

            data = await provider.get_sec_xbrl_statement_table(
                symbol=symbol,
                form=form,
                statement=statement,
                view=view,
                max_rows=max_rows,
            )
            if "error" in data:
                return self._create_error_result(
                    error=ValueError(str(data.get("error"))),
                    metadata={"symbol": symbol},
                )
            return self._create_success_result(data=data, metadata={"symbol": symbol, "form": form})
        except Exception as e:
            logger.error(
                "get_sec_xbrl_statement_table failed", error=str(e), symbol=kwargs.get("symbol")
            )
            return self._create_error_result(error=e, metadata={"symbol": kwargs.get("symbol")})


class FundamentalDataGetSECInsiderForm4Tool(BaseSecEdgarExtendedFundamentalTool):
    """Form 4 insider transactions for an issuer (structured summaries + capped transaction rows)."""

    def get_name(self) -> str:
        return "get_sec_insider_form4"

    def get_description(self) -> str:
        return (
            "SEC EDGAR — **Form 4** insider trading for a **company ticker** (issuers' officers/directors). "
            "Returns recent filings with ``ownership_summary`` (preferred) plus optional transaction rows. "
            "Does not replace a full REST scan of all market insiders; scope is this issuer's Form 4s."
        )

    def get_schema(self) -> ToolSchema:
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Issuer ticker (e.g. 'TSLA', 'AAPL')",
                    },
                    "lookback_days": {
                        "type": "integer",
                        "description": "Only include filings on or after this many days ago",
                        "default": 90,
                    },
                },
                "required": ["symbol"],
            },
            returns={
                "type": "array",
                "description": "Recent Form 4 filings with summaries and transactions",
            },
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        try:
            validated = self.validate_parameters(**kwargs)
            symbol = validated["symbol"]
            lookback_days = validated.get("lookback_days", 90)
            provider = self._provider_for_sec_run()
            data = await provider.get_insider_trading(symbol=symbol, lookback_days=lookback_days)
            return self._create_success_result(
                data=data,
                metadata={
                    "symbol": symbol,
                    "lookback_days": lookback_days,
                    "assumptions": [
                        "Prefer ownership_summary over raw transactions for interpretation.",
                        "Transaction rows per filing are capped for LLM context.",
                    ],
                },
            )
        except Exception as e:
            logger.error("get_sec_insider_form4 failed", error=str(e), symbol=kwargs.get("symbol"))
            return self._create_error_result(error=e, metadata={"symbol": kwargs.get("symbol")})


class FundamentalDataGetSEC13FInstitutionalHoldingsTool(BaseSecEdgarExtendedFundamentalTool):
    """Latest 13F-HR portfolio for an institutional manager (filer)."""

    def get_name(self) -> str:
        return "get_sec_13f_institutional_holdings"

    def get_description(self) -> str:
        return (
            "SEC EDGAR — **13F-HR** quarterly holdings for an **institutional filer** (fund/advisor CIK or ticker). "
            "Returns aggregated positions; **Value** is in **thousands of USD** (multiply by 1000 for dollars). "
            "This is not a shortcut for 'find every fund that owns AAPL' — use a filer you already know, or "
            "search filers separately; EDGAR has no single global 'holders of ticker' endpoint."
        )

    def get_schema(self) -> ToolSchema:
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "filer_symbol_or_cik": {
                        "type": "string",
                        "description": "Investment manager ticker, name, or CIK (e.g. 'BERKSHIRE', '0001067983')",
                    },
                    "max_holdings_rows": {
                        "type": "integer",
                        "description": "Max rows from the holdings table (10–2000)",
                        "default": 400,
                    },
                    "include_holdings_comparison": {
                        "type": "boolean",
                        "description": "Include quarter-over-quarter position change table when prior filing exists",
                        "default": False,
                    },
                    "holding_history_periods": {
                        "type": "integer",
                        "description": "If >0, include multi-quarter share history (0–4 quarters; heavier)",
                        "default": 0,
                    },
                },
                "required": ["filer_symbol_or_cik"],
            },
            returns={"type": "object", "description": "Filer metadata and holdings rows"},
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        try:
            validated = self.validate_parameters(**kwargs)
            filer = validated["filer_symbol_or_cik"]
            max_rows = validated.get("max_holdings_rows", 400)
            inc_cmp = validated.get("include_holdings_comparison", False)
            hist_p = validated.get("holding_history_periods", 0)

            provider = self._provider_for_sec_run()
            if not hasattr(provider, "get_sec_13f_institutional_holdings"):
                return self._create_error_result(
                    error=RuntimeError(
                        "13F holdings require EdgarToolsFundamentalProvider (sec_filings_provider)."
                    ),
                    metadata={"filer_symbol_or_cik": filer},
                )

            data = await provider.get_sec_13f_institutional_holdings(
                filer_symbol_or_cik=filer,
                max_holdings_rows=max_rows,
                include_holdings_comparison=inc_cmp,
                holding_history_periods=hist_p,
            )
            if "error" in data:
                return self._create_error_result(
                    error=ValueError(str(data.get("error"))),
                    metadata={"filer": filer},
                )
            return self._create_success_result(data=data, metadata={"filer": filer})
        except Exception as e:
            logger.error("get_sec_13f_institutional_holdings failed", error=str(e))
            return self._create_error_result(error=e, metadata={})


class FundamentalDataGetSECCompanyEdgarProfileTool(BaseSecEdgarExtendedFundamentalTool):
    """EDGAR entity profile (identity, SIC, float) for routing follow-up tools."""

    def get_name(self) -> str:
        return "get_sec_company_edgar_profile"

    def get_description(self) -> str:
        return (
            "SEC EDGAR — **entity metadata** for a ticker or CIK: name, CIK, SIC, shares outstanding, public float. "
            "Use first to confirm the correct issuer or filer before calling 13F, Form 4, or filings list tools."
        )

    def get_schema(self) -> ToolSchema:
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Ticker symbol or CIK (e.g. 'AAPL' or '0000320193')",
                    },
                },
                "required": ["symbol"],
            },
            returns={"type": "object", "description": "Company / entity metadata from EDGAR"},
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        try:
            validated = self.validate_parameters(**kwargs)
            symbol = validated["symbol"]
            provider = self._provider_for_sec_run()
            if not hasattr(provider, "get_sec_company_edgar_profile"):
                return self._create_error_result(
                    error=RuntimeError(
                        "EDGAR profile requires EdgarToolsFundamentalProvider (sec_filings_provider)."
                    ),
                    metadata={"symbol": symbol},
                )
            data = await provider.get_sec_company_edgar_profile(symbol=symbol)
            return self._create_success_result(data=data, metadata={"symbol": symbol})
        except Exception as e:
            logger.error(
                "get_sec_company_edgar_profile failed", error=str(e), symbol=kwargs.get("symbol")
            )
            return self._create_error_result(error=e, metadata={"symbol": kwargs.get("symbol")})


class FundamentalDataFindSecFundsTool(BaseSecEdgarExtendedFundamentalTool):
    """Search SEC-registered fund series, companies, or share classes by name fragment."""

    def get_name(self) -> str:
        return "find_sec_funds"

    def get_description(self) -> str:
        return (
            "SEC EDGAR — **search mutual funds and ETFs** by name (edgartools ``find_funds``). "
            "Returns matching records (series_id, CIK, class_id, ticker, etc.). "
            "Pass an identifier from a row to **get_sec_fund_entity** for full hierarchy resolution."
        )

    def get_schema(self) -> ToolSchema:
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Name fragment (e.g. 'vanguard', 'growth')",
                    },
                    "search_type": {
                        "type": "string",
                        "enum": ["series", "company", "class"],
                        "description": "What to search: fund series (default), fund company, or share class",
                        "default": "series",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max matches to return (1–100)",
                        "default": 40,
                    },
                },
                "required": ["query"],
            },
            returns={
                "type": "object",
                "description": "Search hits with identifiers usable with get_sec_fund_entity",
            },
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        try:
            validated = self.validate_parameters(**kwargs)
            query = validated["query"]
            search_type = validated.get("search_type", "series")
            limit = validated.get("limit", 40)
            provider = self._provider_for_sec_run()
            if not hasattr(provider, "find_sec_funds"):
                return self._create_error_result(
                    error=RuntimeError(
                        "Fund search requires EdgarToolsFundamentalProvider (sec_filings_provider)."
                    ),
                    metadata={"query": query},
                )
            data = await provider.find_sec_funds(query=query, search_type=search_type, limit=limit)
            if "error" in data:
                return self._create_error_result(
                    error=ValueError(str(data.get("error"))),
                    metadata={"query": query},
                )
            return self._create_success_result(data=data, metadata={"query": query})
        except Exception as e:
            logger.error("find_sec_funds failed", error=str(e))
            return self._create_error_result(error=e, metadata={})


class FundamentalDataGetSecFundEntityTool(BaseSecEdgarExtendedFundamentalTool):
    """Resolve a single fund identifier to company / series / share class (edgartools ``Fund``)."""

    def get_name(self) -> str:
        return "get_sec_fund_entity"

    def get_description(self) -> str:
        return (
            "SEC EDGAR — **resolve a fund** (mutual fund ticker, ETF ticker, series id like S000…, or CIK). "
            "Returns the three-level hierarchy: **FundCompany**, **FundSeries**, **FundClass** (when applicable). "
            "Optionally list all **series** in the company or **share classes** in the series."
        )

    def get_schema(self) -> ToolSchema:
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Ticker (SPY, VFINX), series id (S000…), or investment company CIK",
                    },
                    "include_series_for_company": {
                        "type": "boolean",
                        "description": "List all fund series under the resolved company (e.g. after resolving by CIK)",
                        "default": False,
                    },
                    "include_classes_for_series": {
                        "type": "boolean",
                        "description": "List all share classes in the resolved series (e.g. compare VFINX vs VFIAX)",
                        "default": False,
                    },
                    "max_series": {
                        "type": "integer",
                        "description": "Cap when include_series_for_company is true",
                        "default": 200,
                    },
                    "max_classes": {
                        "type": "integer",
                        "description": "Cap when include_classes_for_series is true",
                        "default": 100,
                    },
                },
                "required": ["identifier"],
            },
            returns={"type": "object", "description": "Resolved fund hierarchy and optional lists"},
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        try:
            validated = self.validate_parameters(**kwargs)
            ident = validated["identifier"]
            provider = self._provider_for_sec_run()
            if not hasattr(provider, "get_sec_fund_entity"):
                return self._create_error_result(
                    error=RuntimeError(
                        "Fund entity resolution requires EdgarToolsFundamentalProvider (sec_filings_provider)."
                    ),
                    metadata={"identifier": ident},
                )
            data = await provider.get_sec_fund_entity(
                ident,
                include_series_for_company=validated.get("include_series_for_company", False),
                include_classes_for_series=validated.get("include_classes_for_series", False),
                max_series=validated.get("max_series", 200),
                max_classes=validated.get("max_classes", 100),
            )
            return self._create_success_result(data=data, metadata={"identifier": ident})
        except Exception as e:
            logger.error("get_sec_fund_entity failed", error=str(e))
            return self._create_error_result(
                error=e, metadata={"identifier": kwargs.get("identifier")}
            )


class FundamentalDataGetSecFundFilingsTool(BaseSecEdgarExtendedFundamentalTool):
    """NPORT-P and other fund filings for a resolved fund entity."""

    def get_name(self) -> str:
        return "get_sec_fund_filings"

    def get_description(self) -> str:
        return (
            "SEC EDGAR — **fund filings** (e.g. NPORT-P portfolio reports) via ``Fund.get_filings``. "
            "Use **series_only=true** to filter with EFTS to filings mentioning the fund's series id."
        )

    def get_schema(self) -> ToolSchema:
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Fund ticker, series id, or CIK (same as get_sec_fund_entity)",
                    },
                    "form": {
                        "type": "string",
                        "description": "SEC form (e.g. NPORT-P, N-MFP3, N-CEN, N-CSR)",
                        "default": "NPORT-P",
                    },
                    "series_only": {
                        "type": "boolean",
                        "description": "If true, narrow to filings that mention this fund's series (EFTS)",
                        "default": False,
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max filings to return (1–50)",
                        "default": 25,
                    },
                },
                "required": ["identifier"],
            },
            returns={
                "type": "object",
                "description": "Filing metadata rows (dates, accession, URLs)",
            },
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        try:
            validated = self.validate_parameters(**kwargs)
            ident = validated["identifier"]
            provider = self._provider_for_sec_run()
            if not hasattr(provider, "get_sec_fund_filings"):
                return self._create_error_result(
                    error=RuntimeError(
                        "Fund filings require EdgarToolsFundamentalProvider (sec_filings_provider)."
                    ),
                    metadata={"identifier": ident},
                )
            data = await provider.get_sec_fund_filings(
                ident,
                form=validated.get("form", "NPORT-P"),
                series_only=validated.get("series_only", False),
                limit=validated.get("limit", 25),
            )
            return self._create_success_result(data=data, metadata={"identifier": ident})
        except Exception as e:
            logger.error("get_sec_fund_filings failed", error=str(e))
            return self._create_error_result(
                error=e, metadata={"identifier": kwargs.get("identifier")}
            )


class FundamentalDataGetSecFundPortfolioTool(BaseSecEdgarExtendedFundamentalTool):
    """Latest disclosed portfolio holdings for a fund or ETF (NPORT chain)."""

    def get_name(self) -> str:
        return "get_sec_fund_portfolio"

    def get_description(self) -> str:
        return (
            "SEC EDGAR — **latest portfolio holdings** for a mutual fund or ETF (``Fund.get_portfolio``). "
            "Returns name, ticker, value_usd, pct_value, and other columns as in the filing extract."
        )

    def get_schema(self) -> ToolSchema:
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Fund ticker (e.g. VFINX, SPY) or other resolvable fund identifier",
                    },
                    "max_rows": {
                        "type": "integer",
                        "description": "Max holdings rows (10–500); top of the table is most material",
                        "default": 150,
                    },
                },
                "required": ["identifier"],
            },
            returns={"type": "object", "description": "Holdings rows and row_count"},
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        try:
            validated = self.validate_parameters(**kwargs)
            ident = validated["identifier"]
            provider = self._provider_for_sec_run()
            if not hasattr(provider, "get_sec_fund_portfolio"):
                return self._create_error_result(
                    error=RuntimeError(
                        "Fund portfolio requires EdgarToolsFundamentalProvider (sec_filings_provider)."
                    ),
                    metadata={"identifier": ident},
                )
            data = await provider.get_sec_fund_portfolio(
                ident,
                max_rows=validated.get("max_rows", 150),
            )
            return self._create_success_result(data=data, metadata={"identifier": ident})
        except Exception as e:
            logger.error("get_sec_fund_portfolio failed", error=str(e))
            return self._create_error_result(
                error=e, metadata={"identifier": kwargs.get("identifier")}
            )


class FundamentalDataGetSecFundLatestReportTool(BaseSecEdgarExtendedFundamentalTool):
    """Latest parsed NPORT (or other form) report: summary fields + sample of investment rows."""

    def get_name(self) -> str:
        return "get_sec_fund_latest_report"

    def get_description(self) -> str:
        return (
            "SEC EDGAR — **latest parsed fund report** (default NPORT-P; optional N-MFP3, N-CEN, N-CSR). "
            "Returns general fund info and a capped sample of **investment_data()** rows. "
            "For full holdings prefer **get_sec_fund_portfolio**."
        )

    def get_schema(self) -> ToolSchema:
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Fund ticker or other resolvable identifier",
                    },
                    "form": {
                        "type": "string",
                        "description": "Optional form override (e.g. N-MFP3, N-CEN, N-CSR). Omit for default NPORT-P.",
                        "default": "",
                    },
                    "max_investment_rows": {
                        "type": "integer",
                        "description": "Cap investment rows in the sample (5–200)",
                        "default": 40,
                    },
                },
                "required": ["identifier"],
            },
            returns={
                "type": "object",
                "description": "general_info, filing metadata, investments_sample",
            },
        )

    async def execute(self, force_refresh: bool = False, **kwargs: Any) -> ToolResult:
        return await self._execute_with_cache(force_refresh=force_refresh, **kwargs)

    async def _execute_impl(self, **kwargs: Any) -> ToolResult:
        try:
            validated = self.validate_parameters(**kwargs)
            ident = validated["identifier"]
            form_raw = validated.get("form") or ""
            form = str(form_raw).strip() or None
            provider = self._provider_for_sec_run()
            if not hasattr(provider, "get_sec_fund_latest_report"):
                return self._create_error_result(
                    error=RuntimeError(
                        "Fund report parsing requires EdgarToolsFundamentalProvider (sec_filings_provider)."
                    ),
                    metadata={"identifier": ident},
                )
            data = await provider.get_sec_fund_latest_report(
                ident,
                form=form,
                max_investment_rows=validated.get("max_investment_rows", 40),
            )
            if "error" in data:
                return self._create_error_result(
                    error=ValueError(str(data.get("error"))),
                    metadata={"identifier": ident},
                )
            return self._create_success_result(data=data, metadata={"identifier": ident})
        except Exception as e:
            logger.error("get_sec_fund_latest_report failed", error=str(e))
            return self._create_error_result(
                error=e, metadata={"identifier": kwargs.get("identifier")}
            )
