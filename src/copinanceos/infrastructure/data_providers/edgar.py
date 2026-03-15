"""SEC EDGAR data provider implementation.

This provider accesses SEC EDGAR database for comprehensive SEC filing data.
"""

import asyncio
import json
import re
from html.parser import HTMLParser
from importlib import resources
from pathlib import Path
from typing import Any

import httpx
import structlog

from copinanceos.domain.models.fundamentals import StockFundamentals
from copinanceos.domain.ports.data_providers import FundamentalDataProvider

logger = structlog.get_logger(__name__)

# Package reference for loading resource files
_RESOURCES_PACKAGE = "copinanceos.infrastructure.data_providers.resources"


class _HTMLTextExtractor(HTMLParser):
    """Simple HTML parser to extract text content."""

    def __init__(self) -> None:
        super().__init__()
        self.text_parts: list[str] = []
        self.skip_tags = {"script", "style", "meta", "link", "head"}
        self.in_skip_tag = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in self.skip_tags:
            self.in_skip_tag = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.skip_tags:
            self.in_skip_tag = False
        elif tag.lower() in {"p", "div", "br", "li"}:
            self.text_parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.in_skip_tag:
            self.text_parts.append(data)

    def get_text(self) -> str:
        """Get extracted text with normalized whitespace."""
        text = "".join(self.text_parts)
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\n\s*\n", "\n\n", text)
        return text.strip()


class EdgarFundamentalProvider(FundamentalDataProvider):
    """SEC EDGAR provider for fundamental data, specializing in SEC filings."""

    def __init__(
        self,
        user_agent: str = "copinance-os/1.0 contact@example.com",
        rate_limit_delay: float = 0.1,
    ) -> None:
        """Initialize EDGAR provider.

        Args:
            user_agent: User agent string (required by SEC EDGAR API)
            rate_limit_delay: Delay between requests in seconds (SEC requires rate limiting)
        """
        self.base_url = "https://data.sec.gov"
        self.user_agent = user_agent
        self.rate_limit_delay = rate_limit_delay
        self._client: httpx.AsyncClient | None = None
        self._cik_cache: dict[str, str] = {}
        self._tickers_data: dict[str, Any] | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={"User-Agent": self.user_agent},
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def is_available(self) -> bool:
        """Check if EDGAR is available."""
        try:
            client = await self._get_client()
            response = await client.get(f"{self.base_url}/", timeout=5.0)
            return bool(response.status_code == 200)
        except Exception as e:
            logger.warning("EDGAR availability check failed", error=str(e))
            return False

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "edgar"

    def _load_tickers_data(self) -> dict[str, Any]:
        """Load company tickers data from local resource file.

        Returns:
            Dictionary mapping ticker symbols to CIK data
        """
        if self._tickers_data is None:
            try:
                # Load from package resource using importlib.resources
                resource_path = resources.files(_RESOURCES_PACKAGE) / "sec_company_tickers.json"

                with (
                    resources.as_file(resource_path) as tickers_file,
                    Path(tickers_file).open(encoding="utf-8") as f,
                ):
                    self._tickers_data = json.load(f)

                logger.debug(
                    "Loaded company tickers from resource file", count=len(self._tickers_data)
                )
            except Exception as e:
                logger.error("Failed to load company tickers resource", error=str(e))
                self._tickers_data = {}

        return self._tickers_data

    async def _get_cik_from_ticker(self, symbol: str) -> str | None:
        """Get CIK (Central Index Key) from ticker symbol.

        Uses local resource file for ticker-to-CIK mapping.

        Args:
            symbol: Stock ticker symbol

        Returns:
            CIK as string (10 digits, zero-padded) or None if not found
        """
        # Check cache first
        if symbol.upper() in self._cik_cache:
            return self._cik_cache[symbol.upper()]

        try:
            # Load tickers data from local resource
            tickers_data = self._load_tickers_data()

            # tickers_data structure: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "..."}, ...}
            for entry in tickers_data.values():
                if entry.get("ticker", "").upper() == symbol.upper():
                    cik = str(entry.get("cik_str", ""))
                    if cik:
                        cik_padded = cik.zfill(10)  # Pad to 10 digits
                        self._cik_cache[symbol.upper()] = cik_padded
                        logger.debug("Found CIK for symbol", symbol=symbol, cik=cik_padded)
                        return cik_padded

            logger.warning("CIK not found for symbol", symbol=symbol)
            return None
        except Exception as e:
            logger.error("Failed to get CIK from ticker", symbol=symbol, error=str(e))
            return None

    async def get_sec_filings(
        self,
        symbol: str,
        filing_types: list[str],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get SEC filings from EDGAR.

        Args:
            symbol: Stock ticker symbol
            filing_types: List of filing types (e.g., ['10-K', '10-Q', '8-K'])
            limit: Maximum number of filings to return

        Returns:
            List of filing dictionaries with metadata
        """
        try:
            cik = await self._get_cik_from_ticker(symbol)
            if not cik:
                logger.warning("Could not find CIK for symbol", symbol=symbol)
                return []

            client = await self._get_client()
            submissions_url = f"{self.base_url}/submissions/CIK{cik}.json"

            await asyncio.sleep(self.rate_limit_delay)  # Rate limiting
            response = await client.get(submissions_url)
            response.raise_for_status()

            data = response.json()
            filings_data = data.get("filings", {}).get("recent", {})
            forms = filings_data.get("form", [])
            filing_dates = filings_data.get("filingDate", [])
            report_dates = filings_data.get("reportDate", [])

            # Filter and format filings
            filings: list[dict[str, Any]] = []
            filing_types_upper = [ft.upper() for ft in filing_types]
            accession_numbers = filings_data.get("accessionNumber", [])

            # Track available form types for better error messages
            available_forms = {form.upper() for form in forms} if forms else set()

            for i, form in enumerate(forms):
                if form.upper() in filing_types_upper:
                    accession_number = accession_numbers[i] if i < len(accession_numbers) else None

                    # Build EDGAR document URL
                    # Format: https://www.sec.gov/cgi-bin/viewer?action=view&cik={CIK}&accession_number={accession}&xbrl_type=v
                    # Or direct: https://www.sec.gov/Archives/edgar/data/{CIK}/{accession_no}/{primary_document}
                    filing_url = None
                    if accession_number:
                        # Construct viewer URL for the filing
                        # This URL allows viewing the filing in SEC's viewer
                        filing_url = (
                            f"https://www.sec.gov/cgi-bin/viewer?action=view&cik={cik}"
                            f"&accession_number={accession_number}&xbrl_type=v"
                        )

                    filing = {
                        "symbol": symbol,
                        "cik": cik,
                        "form_type": form,
                        "filing_date": filing_dates[i] if i < len(filing_dates) else None,
                        "report_date": report_dates[i] if i < len(report_dates) else None,
                        "accession_number": accession_number,
                        "filing_url": filing_url,
                        "description": f"{form} filed on {filing_dates[i] if i < len(filing_dates) else 'N/A'}",
                    }
                    filings.append(filing)

                    if len(filings) >= limit:
                        break

            # Sort by filing date (most recent first)
            filings.sort(key=lambda x: x.get("filing_date", ""), reverse=True)

            # If no filings found, log available form types for debugging
            if len(filings) == 0 and available_forms:
                logger.info(
                    "No filings found for requested types",
                    symbol=symbol,
                    requested_types=filing_types,
                    available_types=list(available_forms)[:10],  # Limit to first 10
                )

            logger.info(
                "Retrieved SEC filings",
                symbol=symbol,
                count=len(filings),
                filing_types=filing_types,
            )
            return filings[:limit]

        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error fetching SEC filings",
                symbol=symbol,
                status_code=e.response.status_code,
                error=str(e),
            )
            return []
        except Exception as e:
            logger.error("Failed to get SEC filings", symbol=symbol, error=str(e))
            return []

    def _extract_text_from_html(self, html_content: str) -> str:
        """Extract clean text from HTML content.

        Args:
            html_content: Raw HTML content

        Returns:
            Clean text with HTML tags removed
        """
        parser = _HTMLTextExtractor()
        parser.feed(html_content)
        return parser.get_text()

    def _extract_text_from_txt(self, txt_content: str) -> str:
        """Extract clean text from .txt filing, removing XML/XBRL sections.

        SEC filings typically have the readable text first, followed by XML/XBRL.
        This method extracts only the text portion before XML markers.

        Args:
            txt_content: Raw .txt file content

        Returns:
            Clean text without XML/XBRL sections
        """
        # Look for common XML/XBRL markers
        xml_markers = [
            r"<xml",
            r"<XBRL",
            r"<xbrl",
            r"<?xml",
            r"<document>",
            r"<DOCUMENT>",
        ]

        # Find the earliest XML marker
        earliest_xml_pos = len(txt_content)
        for marker in xml_markers:
            pattern = re.compile(marker, re.IGNORECASE)
            match = pattern.search(txt_content)
            if match and match.start() < earliest_xml_pos:
                earliest_xml_pos = match.start()

        # Extract text before XML section
        if earliest_xml_pos < len(txt_content):
            text_content = txt_content[:earliest_xml_pos]
        else:
            text_content = txt_content

        # Clean up the text
        # Remove excessive whitespace but preserve paragraph structure
        text_content = re.sub(r"[ \t]+", " ", text_content)  # Multiple spaces to single
        text_content = re.sub(r"\n{3,}", "\n\n", text_content)  # Multiple newlines to double
        text_content = re.sub(r"[^\S\n]+", " ", text_content)  # Multiple non-newline whitespace

        return text_content.strip()

    async def get_sec_filing_content(
        self,
        cik: str,
        accession_number: str,
        document_type: str = "full",
    ) -> dict[str, Any]:
        """Get the content of a specific SEC filing.

        Args:
            cik: Central Index Key (10 digits, zero-padded)
            accession_number: SEC accession number (e.g., "0000320193-23-000077")
            document_type: Type of document to retrieve. Options:
                - "full": Full text filing (default) - may include XML/XBRL
                - "text": Clean text version without XML/XBRL (recommended for LLM analysis)
                - "index": Filing index with document list
                - "html": HTML version if available

        Returns:
            Dictionary with filing content and metadata
        """
        try:
            client = await self._get_client()
            # Remove dashes from accession number for URL construction
            accession_clean = accession_number.replace("-", "")

            # Construct base URL for the filing
            # Format: https://www.sec.gov/Archives/edgar/data/{CIK}/{accession_no}/
            base_filing_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_clean}"

            if document_type == "index":
                # Get the index file which lists all documents in the filing
                index_url = f"{base_filing_url}/index.json"
                await asyncio.sleep(self.rate_limit_delay)
                response = await client.get(index_url)
                response.raise_for_status()
                index_data = response.json()

                return {
                    "cik": cik,
                    "accession_number": accession_number,
                    "document_type": "index",
                    "content": index_data,
                    "url": index_url,
                }

            elif document_type == "html":
                # Try to get HTML version - first get index to find HTML file
                index_url = f"{base_filing_url}/index.json"
                await asyncio.sleep(self.rate_limit_delay)
                response = await client.get(index_url)
                response.raise_for_status()
                index_data = response.json()

                # Find HTML document in the filing
                html_doc = None
                if "directory" in index_data and "item" in index_data["directory"]:
                    for item in index_data["directory"]["item"]:
                        if item.get("type") == "html" or item.get("name", "").endswith(".htm"):
                            html_doc = item.get("name")
                            break

                if html_doc:
                    html_url = f"{base_filing_url}/{html_doc}"
                    await asyncio.sleep(self.rate_limit_delay)
                    html_response = await client.get(html_url)
                    html_response.raise_for_status()
                    return {
                        "cik": cik,
                        "accession_number": accession_number,
                        "document_type": "html",
                        "content": html_response.text,
                        "url": html_url,
                        "document_name": html_doc,
                    }
                else:
                    logger.warning(
                        "HTML document not found, falling back to full text",
                        accession_number=accession_number,
                    )
                    document_type = "full"

            elif document_type == "text":
                # Get clean text version
                # First try HTML version (cleaner), then fall back to .txt with XML removal
                index_url = f"{base_filing_url}/index.json"
                await asyncio.sleep(self.rate_limit_delay)
                index_response = await client.get(index_url)
                index_response.raise_for_status()
                index_data = index_response.json()

                # Try to get HTML first
                html_doc = None
                if "directory" in index_data and "item" in index_data["directory"]:
                    for item in index_data["directory"]["item"]:
                        if item.get("type") == "html" or item.get("name", "").endswith(".htm"):
                            html_doc = item.get("name")
                            break

                if html_doc:
                    html_url = f"{base_filing_url}/{html_doc}"
                    await asyncio.sleep(self.rate_limit_delay)
                    html_response = await client.get(html_url)
                    html_response.raise_for_status()
                    clean_text = self._extract_text_from_html(html_response.text)
                    return {
                        "cik": cik,
                        "accession_number": accession_number,
                        "document_type": "text",
                        "content": clean_text,
                        "url": html_url,
                        "document_name": html_doc,
                        "content_length": len(clean_text),
                        "source": "html",
                    }

                # Fall back to .txt file with XML removal
                # Find primary .txt document
                primary_doc = None
                if "directory" in index_data and "item" in index_data["directory"]:
                    form_type = index_data.get("form")
                    for item in index_data["directory"]["item"]:
                        name = item.get("name", "")
                        if name.endswith(".txt"):
                            if form_type and form_type.lower() in name.lower():
                                primary_doc = item
                                break
                            elif not primary_doc:
                                primary_doc = item

                if not primary_doc:
                    # Try direct accession number format
                    full_text_url = f"{base_filing_url}/{accession_clean}.txt"
                    await asyncio.sleep(self.rate_limit_delay)
                    try:
                        response = await client.get(full_text_url)
                        response.raise_for_status()
                        clean_text = self._extract_text_from_txt(response.text)
                        return {
                            "cik": cik,
                            "accession_number": accession_number,
                            "document_type": "text",
                            "content": clean_text,
                            "url": full_text_url,
                            "content_length": len(clean_text),
                            "source": "txt",
                        }
                    except httpx.HTTPStatusError:
                        return {
                            "cik": cik,
                            "accession_number": accession_number,
                            "document_type": "index",
                            "content": index_data,
                            "url": index_url,
                            "error": "Could not find primary document. Available documents listed in content.",
                        }

                # Get and process .txt file
                doc_name = primary_doc.get("name")
                full_text_url = f"{base_filing_url}/{doc_name}"
                await asyncio.sleep(self.rate_limit_delay)
                response = await client.get(full_text_url)
                response.raise_for_status()
                clean_text = self._extract_text_from_txt(response.text)

                logger.info(
                    "Retrieved clean text from SEC filing",
                    cik=cik,
                    accession_number=accession_number,
                    document_name=doc_name,
                    content_length=len(clean_text),
                )

                return {
                    "cik": cik,
                    "accession_number": accession_number,
                    "document_type": "text",
                    "content": clean_text,
                    "url": full_text_url,
                    "document_name": doc_name,
                    "content_length": len(clean_text),
                    "source": "txt",
                }

            # Default: Get full text filing
            # First, get the index to find the primary document
            index_url = f"{base_filing_url}/index.json"
            await asyncio.sleep(self.rate_limit_delay)
            index_response = await client.get(index_url)
            index_response.raise_for_status()
            index_data = index_response.json()

            # Find the primary document (usually the main filing document)
            # Look for documents with type "10-K", "10-Q", etc. or the primary document
            primary_doc = None
            if "directory" in index_data and "item" in index_data["directory"]:
                # First, try to find a document matching the form type
                form_type = None
                if "form" in index_data:
                    form_type = index_data["form"]

                # Look for primary document - usually the largest text file or the main filing
                for item in index_data["directory"]["item"]:
                    name = item.get("name", "")
                    size = item.get("size", 0)

                    # Prefer documents that match the form type or are large text files
                    if name.endswith(".txt") and (
                        not primary_doc or size > primary_doc.get("size", 0)
                    ):
                        # Check if it matches form type (e.g., "msft-10k_20230630.txt")
                        if form_type and form_type.lower() in name.lower():
                            primary_doc = item
                            break
                        elif not primary_doc:
                            primary_doc = item

                # If no primary doc found, get the first .txt file
                if not primary_doc:
                    for item in index_data["directory"]["item"]:
                        if item.get("name", "").endswith(".txt"):
                            primary_doc = item
                            break

            if not primary_doc:
                # Fallback: try the accession number format
                # Some filings use format like: {accession_clean}.txt
                full_text_url = f"{base_filing_url}/{accession_clean}.txt"
                await asyncio.sleep(self.rate_limit_delay)
                try:
                    response = await client.get(full_text_url)
                    response.raise_for_status()
                    content = response.text
                    return {
                        "cik": cik,
                        "accession_number": accession_number,
                        "document_type": document_type,
                        "content": content,
                        "url": full_text_url,
                        "content_length": len(content),
                    }
                except httpx.HTTPStatusError:
                    # If that fails, return index data so user can see available documents
                    return {
                        "cik": cik,
                        "accession_number": accession_number,
                        "document_type": "index",
                        "content": index_data,
                        "url": index_url,
                        "error": "Could not find primary document. Available documents listed in content.",
                    }

            # Use the primary document name
            doc_name = primary_doc.get("name")
            full_text_url = f"{base_filing_url}/{doc_name}"
            await asyncio.sleep(self.rate_limit_delay)
            response = await client.get(full_text_url)
            response.raise_for_status()

            content = response.text

            logger.info(
                "Retrieved SEC filing content",
                cik=cik,
                accession_number=accession_number,
                document_type=document_type,
                document_name=doc_name,
                content_length=len(content),
            )

            return {
                "cik": cik,
                "accession_number": accession_number,
                "document_type": document_type,
                "content": content,
                "url": full_text_url,
                "document_name": doc_name,
                "content_length": len(content),
            }

        except httpx.HTTPStatusError as e:
            logger.error(
                "HTTP error fetching SEC filing content",
                cik=cik,
                accession_number=accession_number,
                status_code=e.response.status_code,
                error=str(e),
            )
            return {
                "cik": cik,
                "accession_number": accession_number,
                "error": f"HTTP {e.response.status_code}: {str(e)}",
            }
        except Exception as e:
            logger.error(
                "Failed to get SEC filing content",
                cik=cik,
                accession_number=accession_number,
                error=str(e),
            )
            return {
                "cik": cik,
                "accession_number": accession_number,
                "error": str(e),
            }

    async def get_financial_statements(
        self,
        symbol: str,
        statement_type: str,
        period: str = "annual",
    ) -> dict[str, Any]:
        """Get financial statements.

        Note: EDGAR provider focuses on SEC filings. For financial statements,
        consider using a provider that specializes in parsed financial data.

        Args:
            symbol: Stock ticker symbol
            statement_type: Type of statement (income_statement, balance_sheet, cash_flow)
            period: Period type (annual, quarterly)

        Returns:
            Empty dict - EDGAR doesn't provide parsed financial statements
        """
        logger.warning(
            "EDGAR provider does not provide parsed financial statements",
            symbol=symbol,
            suggestion="Use a provider that specializes in financial statements",
        )
        return {}

    async def get_earnings_transcripts(
        self,
        symbol: str,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        """Get earnings call transcripts.

        Note: EDGAR doesn't provide earnings transcripts.

        Args:
            symbol: Stock ticker symbol
            limit: Maximum number of transcripts

        Returns:
            Empty list
        """
        logger.warning(
            "EDGAR provider does not provide earnings transcripts",
            symbol=symbol,
        )
        return []

    async def get_esg_metrics(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """Get ESG metrics.

        Note: EDGAR doesn't provide ESG metrics.

        Args:
            symbol: Stock ticker symbol

        Returns:
            Empty dict
        """
        logger.warning("EDGAR provider does not provide ESG metrics", symbol=symbol)
        return {}

    async def get_insider_trading(
        self,
        symbol: str,
        lookback_days: int = 90,
    ) -> list[dict[str, Any]]:
        """Get insider trading activity.

        Note: EDGAR provides Form 4 filings which contain insider trading data,
        but this implementation doesn't parse them yet.

        Args:
            symbol: Stock ticker symbol
            lookback_days: Number of days to look back

        Returns:
            Empty list (not yet implemented)
        """
        logger.warning(
            "Insider trading parsing not yet implemented for EDGAR provider",
            symbol=symbol,
        )
        return []

    async def get_detailed_fundamentals(
        self,
        symbol: str,
        periods: int = 5,
        period_type: str = "annual",
    ) -> StockFundamentals:
        """Get detailed fundamentals.

        Note: EDGAR provider focuses on SEC filings. For comprehensive fundamentals,
        use a provider that specializes in parsed financial data.

        Args:
            symbol: Stock ticker symbol
            periods: Number of periods
            period_type: Period type (annual, quarterly)

        Returns:
            Raises NotImplementedError - use a provider that specializes in fundamentals
        """
        raise NotImplementedError(
            "EDGAR provider does not provide detailed fundamentals. "
            "Use a provider that specializes in parsed financial data."
        )

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
