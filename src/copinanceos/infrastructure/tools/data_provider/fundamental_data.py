"""Fundamental data provider tools."""

from typing import Any

import structlog

from copinanceos.domain.models.tool_results import ToolResult
from copinanceos.domain.ports.data_providers import FundamentalDataProvider
from copinanceos.domain.ports.tools import ToolSchema
from copinanceos.infrastructure.cache import CacheManager
from copinanceos.infrastructure.tools.data_provider.base import BaseDataProviderTool
from copinanceos.infrastructure.tools.data_provider.provider_selector import (
    MultiProviderSelector,
    ProviderSelector,
)

logger = structlog.get_logger(__name__)


class FundamentalDataGetFundamentalsTool(BaseDataProviderTool[FundamentalDataProvider]):
    """Tool for getting detailed stock fundamentals."""

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
        return "get_stock_fundamentals"

    def get_description(self) -> str:
        """Get tool description."""
        return "Get comprehensive fundamental data for a stock including financial statements, ratios, and metrics."

    def get_schema(self) -> ToolSchema:
        """Get tool schema."""
        return self._build_schema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol (e.g., 'AAPL', 'MSFT')",
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
            "Get financial statements (income statement, balance sheet, or cash flow) for a stock."
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
                        "description": "Stock ticker symbol (e.g., 'AAPL', 'MSFT')",
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

    This tool supports provider selection, allowing it to use a different provider
    (e.g., EDGAR) specifically for SEC filings while other tools use the default provider.
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
                raise ValueError("No provider available for SEC filings tool")
            super().__init__(selected_provider, cache_manager=cache_manager, use_cache=use_cache)
        else:
            super().__init__(provider, cache_manager=cache_manager, use_cache=use_cache)

    def get_name(self) -> str:
        """Get tool name."""
        return "get_sec_filings"

    def get_description(self) -> str:
        """Get tool description."""
        return (
            "Get SEC filings (10-K, 10-Q, 8-K, etc.) for a stock from EDGAR database. "
            "Returns filing metadata including filing dates, report dates, accession numbers, and URLs. "
            "10-K filings are annual reports, 10-Q filings are quarterly reports."
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
                        "description": "Stock ticker symbol (e.g., 'AAPL', 'MSFT')",
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
                raise ValueError("No provider available for SEC filing content tool")
            super().__init__(selected_provider, cache_manager=cache_manager, use_cache=use_cache)
        else:
            super().__init__(provider, cache_manager=cache_manager, use_cache=use_cache)

    def get_name(self) -> str:
        """Get tool name."""
        return "get_sec_filing_content"

    def get_description(self) -> str:
        """Get tool description."""
        return (
            "Download the full content of a specific SEC filing (10-K, 10-Q, etc.) by CIK and accession number. "
            "Returns the complete text content of the filing for analysis. "
            "Use this tool after getting filing metadata from get_sec_filings to read the actual report content."
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
                        "Use EDGAR provider for this functionality."
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
