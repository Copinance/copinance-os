"""SEC EDGAR data via `edgartools` (import package `edgar`).

See https://edgartools.readthedocs.io/ — identity is required by the SEC for programmatic access.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import pandas as pd
import structlog
from edgar import Company, set_identity

from copinance_os.data.cache import CacheManager
from copinance_os.domain.models.fundamentals import StockFundamentals
from copinance_os.domain.ports.data_providers import FundamentalDataProvider

logger = structlog.get_logger(__name__)

# Max text/HTML returned to agent tools (avoid multi‑MB prompts).
_DEFAULT_CONTENT_CHAR_CAP = 500_000

# TTLs for SEC/EDGAR responses (reduce load on sec.gov; filing content is immutable per accession).
_TTL_SEC_FILINGS = timedelta(hours=6)
_TTL_SEC_FILING_CONTENT = timedelta(hours=48)
_TTL_FINANCIAL_STATEMENTS = timedelta(hours=12)
_TTL_INSIDER = timedelta(hours=6)
_TTL_DETAILED_FUNDAMENTALS = timedelta(hours=24)


def _resolve_identity(explicit: str | None) -> str | None:
    if explicit and str(explicit).strip():
        return str(explicit).strip()
    env_first = (os.environ.get("EDGAR_IDENTITY") or "").strip()
    if env_first:
        return env_first
    return (os.environ.get("COPINANCEOS_EDGAR_IDENTITY") or "").strip() or None


def _cik_for_company(symbol_or_cik: str) -> str:
    s = str(symbol_or_cik).strip()
    if s.isdigit():
        return str(int(s))  # normalize leading zeros for lookup
    return s.upper()


def _parse_cik_int(cik: str) -> int:
    digits = "".join(c for c in str(cik) if c.isdigit())
    if not digits:
        raise ValueError(f"Invalid CIK: {cik}")
    return int(digits)


def _stock_fundamentals_minimal(
    *,
    symbol: str,
    company_name: str | None,
    provider: str,
    data_as_of: datetime,
    metadata: dict[str, str],
) -> StockFundamentals:
    """Build StockFundamentals with optional fields explicit (pydantic/mypy)."""
    return StockFundamentals(
        symbol=symbol,
        company_name=company_name,
        sector=None,
        industry=None,
        income_statements=[],
        balance_sheets=[],
        cash_flow_statements=[],
        ratios=None,
        market_cap=None,
        enterprise_value=None,
        current_price=None,
        shares_outstanding=None,
        float_shares=None,
        provider=provider,
        data_as_of=data_as_of,
        fiscal_year_end=None,
        currency=None,
        metadata=metadata,
    )


class EdgarToolsFundamentalProvider(FundamentalDataProvider):
    """Fundamental/SEC provider backed by edgartools (`pip install edgartools`).

    Use for SEC filings, filing text/HTML, and XBRL-based financial statements from EDGAR.
    Configure identity via ``COPINANCEOS_EDGAR_IDENTITY`` or ``EDGAR_IDENTITY`` (Name + email).
    """

    def __init__(
        self,
        identity: str | None = None,
        content_char_cap: int = _DEFAULT_CONTENT_CHAR_CAP,
        cache_manager: CacheManager | None = None,
    ) -> None:
        self._explicit_identity = identity
        self._content_char_cap = content_char_cap
        self._cache_manager = cache_manager
        self._provider_name = "edgartools"
        self._identity_applied = False

    async def _cached_edgar(
        self,
        op: str,
        ttl: timedelta,
        key_kwargs: dict[str, Any],
        sync_fetch: Any,
        *,
        dump: Any = None,
        load: Any = None,
        store_if: Callable[[Any], bool] | None = None,
    ) -> Any:
        """Load through CacheManager when configured; otherwise call edgartools in a thread."""
        if self._cache_manager is None:
            data = await self._call(sync_fetch)
            return load(data) if load else data

        tool = f"edgartools.{op}"
        entry = await self._cache_manager.get(tool, **key_kwargs)
        if entry is not None:
            logger.debug("edgartools cache hit", operation=op)
            raw = entry.data
            return load(raw) if load else raw

        data = await self._call(sync_fetch)
        if store_if is not None and not store_if(data):
            return data
        to_store = dump(data) if dump else data
        await self._cache_manager.set(tool, to_store, ttl=ttl, **key_kwargs)
        return data

    def _ensure_identity(self) -> str:
        ident = _resolve_identity(self._explicit_identity)
        if not ident:
            raise ValueError(
                "SEC EDGAR identity is not set. Set COPINANCEOS_EDGAR_IDENTITY or "
                "EDGAR_IDENTITY to 'Your Name your.email@example.com' (required by the SEC)."
            )
        if not self._identity_applied:
            set_identity(ident)
            self._identity_applied = True
            logger.debug("edgartools identity configured")
        return ident

    async def is_available(self) -> bool:
        try:
            if _resolve_identity(self._explicit_identity) is None:
                return False
            self._ensure_identity()
            return True
        except Exception as e:
            logger.warning("edgartools availability check failed", error=str(e))
            return False

    def get_provider_name(self) -> str:
        return self._provider_name

    @staticmethod
    async def _call(fn: Any, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(fn, *args, **kwargs)

    def _company(self, symbol: str) -> Any:
        self._ensure_identity()
        key = _cik_for_company(symbol)
        return Company(key)

    async def get_financial_statements(
        self,
        symbol: str,
        statement_type: str,
        period: str = "annual",
    ) -> dict[str, Any]:
        if statement_type not in ("income_statement", "balance_sheet", "cash_flow"):
            raise ValueError(f"Invalid statement_type: {statement_type}")
        if period not in ("annual", "quarterly"):
            raise ValueError(f"Invalid period: {period}")

        def _fetch() -> dict[str, Any]:
            co = self._company(symbol)
            fin = co.get_financials() if period == "annual" else co.get_quarterly_financials()
            if statement_type == "income_statement":
                stmt = fin.income_statement()
            elif statement_type == "balance_sheet":
                stmt = fin.balance_sheet()
            else:
                stmt = fin.cashflow_statement()
            df = stmt.to_dataframe()
            df = df.where(pd.notna(df), None)
            records = df.to_dict(orient="records")
            return {
                "symbol": symbol.upper(),
                "statement_type": statement_type,
                "period": period,
                "columns": [str(c) for c in df.columns],
                "data": records,
                "provider": self._provider_name,
            }

        key_kwargs = {
            "symbol": symbol.upper(),
            "statement_type": statement_type,
            "period": period,
        }
        try:
            return cast(
                dict[str, Any],
                await self._cached_edgar(
                    "get_financial_statements",
                    _TTL_FINANCIAL_STATEMENTS,
                    key_kwargs,
                    _fetch,
                ),
            )
        except Exception as e:
            logger.error(
                "edgartools get_financial_statements failed",
                symbol=symbol,
                error=str(e),
            )
            raise ValueError(f"Failed to fetch financial statement for {symbol}: {e}") from e

    async def get_sec_filings(
        self,
        symbol: str,
        filing_types: list[str],
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        if not filing_types:
            filing_types = ["10-K", "10-Q"]

        def _fetch() -> list[dict[str, Any]]:
            co = self._company(symbol)
            rows: list[tuple[str, dict[str, Any]]] = []
            seen_forms: set[str] = set()
            for form in filing_types:
                ft = str(form).strip().upper()
                if not ft or ft in seen_forms:
                    continue
                seen_forms.add(ft)
                batch = co.get_filings(form=ft).head(limit)
                for i in range(len(batch)):
                    f = batch[i]
                    cik_str = str(f.cik).zfill(10)
                    rows.append(
                        (
                            str(f.filing_date),
                            {
                                "symbol": symbol.upper(),
                                "form": f.form,
                                "filing_date": str(f.filing_date),
                                "accession_number": f.accession_number,
                                "cik": cik_str,
                                "filing_url": f.filing_url or getattr(f, "homepage_url", None),
                                "provider": self._provider_name,
                            },
                        )
                    )
            rows.sort(key=lambda x: x[0], reverse=True)
            return [r[1] for r in rows[:limit]]

        key_kwargs = {
            "symbol": symbol.upper(),
            "filing_types": sorted(str(f).strip().upper() for f in filing_types if str(f).strip()),
            "limit": limit,
        }
        try:
            return cast(
                list[dict[str, Any]],
                await self._cached_edgar(
                    "get_sec_filings",
                    _TTL_SEC_FILINGS,
                    key_kwargs,
                    _fetch,
                ),
            )
        except Exception as e:
            logger.error("edgartools get_sec_filings failed", symbol=symbol, error=str(e))
            raise ValueError(f"Failed to fetch SEC filings for {symbol}: {e}") from e

    async def get_sec_filing_content(
        self,
        cik: str,
        accession_number: str,
        document_type: str = "full",
    ) -> dict[str, Any]:
        """Download filing body (extension used by agent tools; not on the abstract port)."""

        def _fetch() -> dict[str, Any]:
            self._ensure_identity()
            co = Company(_parse_cik_int(cik))
            filings = co.get_filings(accession_number=accession_number)
            if len(filings) < 1:
                return {"error": f"No filing found for accession {accession_number}"}
            f = filings[0]
            dt = (document_type or "full").lower()
            if dt == "html":
                body = f.html()
            elif dt == "index":
                body = getattr(f, "homepage_url", None) or getattr(f, "filing_url", "") or ""
            else:
                body = f.text()
            truncated = False
            cap = self._content_char_cap
            text_out = str(body)
            if len(text_out) > cap:
                text_out = text_out[:cap]
                truncated = True
            return {
                "cik": str(cik).zfill(10),
                "accession_number": accession_number,
                "document_type": document_type,
                "content": text_out,
                "truncated": truncated,
                "char_cap": cap,
                "form": getattr(f, "form", None),
                "filing_date": str(getattr(f, "filing_date", "")),
                "provider": self._provider_name,
            }

        key_kwargs = {
            "cik": str(cik).zfill(10),
            "accession_number": accession_number,
            "document_type": (document_type or "full").lower(),
        }
        try:
            return cast(
                dict[str, Any],
                await self._cached_edgar(
                    "get_sec_filing_content",
                    _TTL_SEC_FILING_CONTENT,
                    key_kwargs,
                    _fetch,
                    store_if=lambda d: "error" not in d,
                ),
            )
        except Exception as e:
            logger.error(
                "edgartools get_sec_filing_content failed",
                cik=cik,
                accession_number=accession_number,
                error=str(e),
            )
            return {"error": str(e)}

    async def get_earnings_transcripts(
        self,
        symbol: str,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        logger.warning(
            "edgartools does not provide earnings call transcripts",
            symbol=symbol,
        )
        return []

    async def get_esg_metrics(self, symbol: str) -> dict[str, Any]:
        logger.warning("edgartools does not provide ESG metrics bundle", symbol=symbol)
        return {"error": "ESG metrics not available from edgartools", "symbol": symbol.upper()}

    async def get_insider_trading(
        self,
        symbol: str,
        lookback_days: int = 90,
    ) -> list[dict[str, Any]]:
        def _fetch() -> list[dict[str, Any]]:
            co = self._company(symbol)
            form4s = co.get_filings(form="4").head(25)
            out: list[dict[str, Any]] = []
            for i in range(len(form4s)):
                filing = form4s[i]
                row: dict[str, Any] = {
                    "symbol": symbol.upper(),
                    "form": filing.form,
                    "filing_date": str(filing.filing_date),
                    "accession_number": filing.accession_number,
                    "provider": self._provider_name,
                }
                try:
                    obj = filing.obj()
                    if hasattr(obj, "to_dataframe"):
                        df = obj.to_dataframe()
                        if df is not None and not df.empty:
                            row["transactions"] = df.fillna("").to_dict(orient="records")
                except Exception as ex:
                    row["parse_note"] = str(ex)
                out.append(row)
            return out

        key_kwargs = {"symbol": symbol.upper(), "lookback_days": lookback_days}
        try:
            return cast(
                list[dict[str, Any]],
                await self._cached_edgar(
                    "get_insider_trading",
                    _TTL_INSIDER,
                    key_kwargs,
                    _fetch,
                ),
            )
        except Exception as e:
            logger.error("edgartools get_insider_trading failed", symbol=symbol, error=str(e))
            return []

    async def get_detailed_fundamentals(
        self,
        symbol: str,
        periods: int = 5,
        period_type: str = "annual",
    ) -> StockFundamentals:
        """Minimal snapshot (company name); prefer ``get_financial_statements`` or YFinance for full ratios."""

        def _fetch_sync() -> StockFundamentals:
            co = self._company(symbol)
            try:
                name = co.name
            except Exception:
                name = None
            return _stock_fundamentals_minimal(
                symbol=symbol.upper(),
                company_name=name,
                provider=self._provider_name,
                data_as_of=datetime.now(UTC),
                metadata={
                    "note": (
                        "Minimal EDGAR snapshot from edgartools. For full statements in tools use "
                        "get_financial_statements; for ratio-heavy workflows use "
                        "YFinanceFundamentalProvider."
                    ),
                    "periods_requested": str(periods),
                    "period_type": period_type,
                },
            )

        key_kwargs = {
            "symbol": symbol.upper(),
            "periods": periods,
            "period_type": period_type,
        }
        try:
            return cast(
                StockFundamentals,
                await self._cached_edgar(
                    "get_detailed_fundamentals",
                    _TTL_DETAILED_FUNDAMENTALS,
                    key_kwargs,
                    _fetch_sync,
                    dump=lambda m: m.model_dump(mode="json"),
                    load=lambda d: StockFundamentals.model_validate(d),
                ),
            )
        except Exception as e:
            logger.warning(
                "edgartools get_detailed_fundamentals failed",
                symbol=symbol,
                error=str(e),
            )
            return _stock_fundamentals_minimal(
                symbol=symbol.upper(),
                company_name=None,
                provider=self._provider_name,
                data_as_of=datetime.now(UTC),
                metadata={
                    "note": "edgartools lookup failed; see error in logs",
                    "periods_requested": str(periods),
                    "period_type": period_type,
                    "error": str(e),
                },
            )
