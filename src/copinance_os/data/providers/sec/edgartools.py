"""SEC EDGAR data via `edgartools` (import package `edgar`).

See https://edgartools.readthedocs.io/ — identity is required by the SEC for programmatic access.

**Choosing an API (high level):** one-company multi-period trends → Company Facts / ``get_facts``-style paths;
cross-company standardized metrics → Financials / ``get_financials()``; segments, footnotes, or rare concepts →
XBRL on a specific filing. Start with the simplest layer that answers the question.

Implementation notes (aligned with edgartools docs):

- **Standard statements**: Prefer ``Company.get_financials()`` / ``get_quarterly_financials()`` and call
  ``to_dataframe()`` on each statement object — not raw ``filing.xbrl()`` for primary three statements.
  Use ``get_facts()`` only when you need longer history than the financials bundle (not used here until
  the provider API exposes a period depth).
- **Amounts**: Values from the financials API are **whole USD** (not thousands/millions).
- **Filings**: Always ``.head(n)`` before iterating; avoid ``list(get_filings())[:n]``.
- **Form 4**: Prefer ``filing.obj().get_ownership_summary()`` over ad-hoc DataFrame parsing.
- **13F**: Holdings ``Value`` and summary ``total_value`` are in **thousands of USD**; multiply by 1000 for dollars.
  Use the **filer** (manager) CIK/ticker, not the portfolio company, to list a fund's positions.
- **Registered funds / ETFs**: Use ``edgar.Fund`` and ``find_funds()`` — hierarchy (company, series, share class),
  NPORT-P filings, portfolio holdings, and parsed reports (see ``get_sec_fund_*`` provider methods).
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, cast

import pandas as pd
import structlog
from edgar import Company, Fund, find_funds, set_identity
from typing_extensions import override

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
_TTL_COMPANY_FACTS = timedelta(hours=12)
_TTL_COMPARE_FINANCIALS = timedelta(hours=12)
_TTL_XBRL_STATEMENT = timedelta(hours=24)
_TTL_13F_HOLDINGS = timedelta(hours=12)
_TTL_EDGAR_COMPANY_PROFILE = timedelta(hours=24)
_TTL_FUND_ENTITY = timedelta(hours=12)
_TTL_FUND_SEARCH = timedelta(hours=12)
_TTL_FUND_FILINGS = timedelta(hours=6)
_TTL_FUND_PORTFOLIO = timedelta(hours=6)
_TTL_FUND_REPORT = timedelta(hours=6)

_MAX_COMPANY_FACT_LINE_ITEMS = 120
_MAX_XBRL_TABLE_ROWS = 350
_MAX_INSIDER_TX_ROWS_PER_FILING = 60
_MAX_13F_COMPARE_ROWS = 200
_MAX_13F_HISTORY_ROWS = 120
_MAX_FUND_SEARCH_RESULTS = 100
_MAX_FUND_FILINGS_RETURN = 50
_MAX_FUND_SERIES_LIST = 400
_MAX_FUND_CLASSES_LIST = 200
_MAX_FUND_PORTFOLIO_ROWS = 500


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


def _filing_date_to_date(filing_date: Any) -> date | None:
    if filing_date is None:
        return None
    if isinstance(filing_date, datetime):
        return filing_date.date()
    if isinstance(filing_date, date):
        return filing_date
    try:
        parsed = pd.Timestamp(filing_date)
        if pd.isna(parsed):
            return None
        return parsed.date()
    except Exception:
        return None


def _statement_from_financials(financials: Any, statement_type: str) -> Any:
    """Resolve income / balance / cash flow statement per edgartools Financials API."""
    if statement_type == "income_statement":
        return financials.income_statement()
    if statement_type == "balance_sheet":
        return financials.balance_sheet()
    # Canonical name is cashflow_statement(); cash_flow_statement() is an alias in edgartools.
    return financials.cashflow_statement()


def _statement_to_records(stmt: Any) -> tuple[list[str], list[dict[str, Any]]]:
    """Call ``to_dataframe()`` on a statement (not on the Financials object)."""
    if stmt is None:
        return [], []
    try:
        to_df = getattr(stmt, "to_dataframe", None)
        if not callable(to_df):
            return [], []
        df = to_df()
    except Exception as e:
        logger.warning("edgartools statement to_dataframe failed", error=str(e))
        return [], []
    if df is None or getattr(df, "empty", True):
        return [], []
    df = df.where(pd.notna(df), None)
    columns = [str(c) for c in df.columns]
    records = df.to_dict(orient="records")
    return columns, records


def _serialize_ownership_summary(summary: Any) -> dict[str, Any]:
    """Map edgartools ``OwnershipSummary`` / ``TransactionSummary`` to JSON-friendly dict."""
    out: dict[str, Any] = {
        "insider_name": getattr(summary, "insider_name", None),
        "issuer_name": getattr(summary, "issuer_name", None),
        "issuer_ticker": getattr(summary, "issuer_ticker", None),
        "position": getattr(summary, "position", None),
        "reporting_date": str(getattr(summary, "reporting_date", "") or ""),
        "form_type": str(getattr(summary, "form_type", "") or ""),
        "remarks": getattr(summary, "remarks", None) or "",
    }
    if hasattr(summary, "primary_activity"):
        out["primary_activity"] = summary.primary_activity
    if hasattr(summary, "net_change"):
        try:
            out["net_shares_change"] = int(summary.net_change)
        except (TypeError, ValueError):
            out["net_shares_change"] = None
    if hasattr(summary, "net_value"):
        try:
            out["net_value_usd"] = float(summary.net_value)
        except (TypeError, ValueError):
            out["net_value_usd"] = None
    if hasattr(summary, "remaining_shares"):
        rs = summary.remaining_shares
        out["remaining_shares"] = int(rs) if rs is not None and not pd.isna(rs) else None
    if hasattr(summary, "has_derivative_transactions"):
        out["has_derivative_transactions"] = bool(summary.has_derivative_transactions)
    if hasattr(summary, "transaction_types"):
        out["transaction_types"] = list(summary.transaction_types)
    if hasattr(summary, "total_shares"):
        with contextlib.suppress(TypeError, ValueError):
            out["total_shares"] = int(summary.total_shares)
    return out


def _insider_fetch_head_size(lookback_days: int) -> int:
    """Cap Form 4 fetch size; filter by ``lookback_days`` after fetch."""
    return max(25, min(100, 10 + lookback_days // 3))


def _df_to_records_capped(df: Any, max_rows: int) -> tuple[list[dict[str, Any]], bool, int]:
    """Convert DataFrame to JSON-safe rows with a hard row cap for LLM payloads."""
    if df is None or getattr(df, "empty", True):
        return [], False, 0
    n = len(df)
    truncated = n > max_rows
    sub = df.head(max_rows) if truncated else df
    sub = sub.where(pd.notna(sub), None)
    return sub.to_dict(orient="records"), truncated, max(0, n - max_rows)


def _sec_company_edgar_profile_sync(co: Any, symbol: str, provider_name: str) -> dict[str, Any]:
    """Company/entity metadata from EDGAR (single network round-trip to submissions)."""

    def _safe(name: str) -> Any:
        try:
            return getattr(co, name)
        except Exception:
            return None

    name = _safe("name")
    cik = _safe("cik")
    sic = _safe("sic_code") or _safe("sic")
    sic_desc = _safe("sic_description")
    tickers = _safe("tickers")
    if tickers is not None and not isinstance(tickers, list):
        try:
            tickers = list(tickers)
        except Exception:
            tickers = None

    return {
        "query": str(symbol).strip().upper(),
        "name": name,
        "cik": str(cik) if cik is not None else None,
        "sic_code": str(sic) if sic is not None else None,
        "sic_description": sic_desc,
        "tickers": tickers,
        "shares_outstanding": _safe("shares_outstanding"),
        "public_float": _safe("public_float"),
        "provider": provider_name,
        "api": "Company_EDGAR_entity",
        "assumptions": [
            "Resolved via edgartools Company() (SEC submissions). Fields may be null if not in the feed.",
            "For operating companies use listing ticker; for 13F filers use manager name, ticker, or CIK.",
        ],
    }


def _sec_13f_holdings_sync(
    co: Any,
    *,
    max_holdings_rows: int,
    include_holdings_comparison: bool,
    holding_history_periods: int,
    provider_name: str,
) -> dict[str, Any]:
    """Latest 13F-HR portfolio for an institutional filer (manager), not a stock's holders list."""
    batch = co.get_filings(form="13F-HR", amendments=False).head(1)
    if len(batch) < 1:
        return {
            "error": "No 13F-HR filings found for this entity.",
            "hint": "Use the investment manager's CIK or known ticker (e.g. filer), not a random stock. "
            "EDGAR does not offer a single call for 'all funds holding AAPL' without scanning filers.",
            "provider": provider_name,
        }
    filing = batch[0]
    try:
        tf = filing.obj()
    except Exception as ex:
        return {"error": f"Failed to parse 13F: {ex}", "provider": provider_name}

    holdings = tf.holdings
    rows, trunc, omitted = _df_to_records_capped(holdings, max_holdings_rows)

    tv = getattr(tf, "total_value", None)
    try:
        tv_f = float(tv) if tv is not None else None
    except (TypeError, ValueError):
        tv_f = None
    total_value_usd_approx = tv_f * 1000.0 if tv_f is not None else None

    mgr = None
    gm = getattr(tf, "get_manager_info_summary", None)
    if callable(gm):
        try:
            mgr = gm()
        except Exception:
            mgr = None

    out: dict[str, Any] = {
        "filer": {
            "management_company_name": getattr(tf, "management_company_name", None),
            "manager_name": getattr(tf, "manager_name", None),
            "investment_manager": getattr(tf, "investment_manager", None),
            "report_period": getattr(tf, "report_period", None),
            "filing_date": getattr(tf, "filing_date", None),
            "accession_number": getattr(tf, "accession_number", None),
            "form": getattr(tf, "form", None),
            "manager_info_summary": mgr,
        },
        "portfolio": {
            "total_value_reported_thousands_usd": tv_f,
            "total_value_approx_usd": total_value_usd_approx,
            "total_holdings_count": getattr(tf, "total_holdings", None),
            "holdings_rows": rows,
            "holdings_truncated": trunc,
            "holdings_rows_omitted": omitted,
        },
        "provider": provider_name,
        "api": "ThirteenF_13F_HR",
        "assumptions": [
            "13F values are filed in thousands of USD; 'total_value_approx_usd' multiplies summary total by 1000.",
            "Report is as-of quarter-end; filing can be up to ~45 days later.",
            "CUSIP is the most reliable security key; Ticker may be missing for some lines.",
        ],
    }

    if include_holdings_comparison:
        cmp_fn = getattr(tf, "compare_holdings", None)
        if callable(cmp_fn):
            try:
                comp = cmp_fn(display_limit=_MAX_13F_COMPARE_ROWS)
                if comp is not None and getattr(comp, "data", None) is not None:
                    cr, ctr, co_ = _df_to_records_capped(comp.data, _MAX_13F_COMPARE_ROWS)
                    out["quarter_over_quarter"] = {
                        "rows": cr,
                        "truncated": ctr,
                        "rows_omitted": co_,
                        "current_period": getattr(comp, "current_period", None),
                        "previous_period": getattr(comp, "previous_period", None),
                    }
            except Exception as ex:
                out["quarter_over_quarter_error"] = str(ex)

    if holding_history_periods > 0:
        hh_fn = getattr(tf, "holding_history", None)
        if callable(hh_fn):
            try:
                hist = hh_fn(
                    periods=min(4, holding_history_periods), display_limit=_MAX_13F_HISTORY_ROWS
                )
                if hist is not None and getattr(hist, "data", None) is not None:
                    hr, htr, ho_ = _df_to_records_capped(hist.data, _MAX_13F_HISTORY_ROWS)
                    out["holding_history"] = {
                        "periods": getattr(hist, "periods", None),
                        "rows": hr,
                        "truncated": htr,
                        "rows_omitted": ho_,
                    }
            except Exception as ex:
                out["holding_history_error"] = str(ex)

    return out


def _truncate_company_facts_dict(data: dict[str, Any], max_items: int) -> dict[str, Any]:
    items = data.get("items")
    if not isinstance(items, list) or len(items) <= max_items:
        return data
    out = {
        **data,
        "items": items[:max_items],
        "items_truncated": True,
        "items_omitted": len(items) - max_items,
    }
    return out


def _fill_company_facts_items_from_flat_if_needed(stmt: Any, raw: dict[str, Any]) -> None:
    """If to_dict() yields no rows but facts exist, use to_flat_list() (tabular period columns)."""
    items = raw.get("items")
    meta = raw.get("metadata")
    total = int(meta.get("total_items") or 0) if isinstance(meta, dict) else 0
    if not isinstance(items, list) or len(items) > 0 or total <= 0:
        return
    flat_fn = getattr(stmt, "to_flat_list", None)
    if not callable(flat_fn):
        return
    try:
        rows = flat_fn()
    except Exception:
        logger.warning("company_facts to_flat_list failed", exc_info=True)
        return
    period_cols = raw.get("periods")
    if not isinstance(period_cols, list):
        period_cols = []
    rebuilt: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        vals = {str(c): row.get(c) for c in period_cols}
        if not any(v is not None for v in vals.values()):
            continue
        rebuilt.append(
            {
                "concept": row.get("concept"),
                "label": row.get("label"),
                "depth": row.get("depth"),
                "values": vals,
            }
        )
        if len(rebuilt) >= _MAX_COMPANY_FACT_LINE_ITEMS:
            break
    if rebuilt:
        raw["items"] = rebuilt
        raw["items_layout"] = "flat_period_columns"


def _company_facts_statement_sync(
    *,
    co: Any,
    symbol: str,
    statement_kind: str,
    periods: int,
    period: str,
    line_label: str | None,
    provider_name: str,
) -> dict[str, Any]:
    """Build Company Facts (EntityFacts) multi-period statement payload for one ticker."""
    p = period.lower()
    if p not in ("annual", "quarterly"):
        raise ValueError("period must be 'annual' or 'quarterly'")
    sk = statement_kind.lower()
    if sk == "income_statement":
        stmt = co.income_statement(periods=periods, period=p, as_dataframe=False)
    elif sk == "balance_sheet":
        stmt = co.balance_sheet(periods=periods, period=p, as_dataframe=False)
    elif sk in ("cash_flow", "cashflow_statement", "cash_flow_statement"):
        stmt = co.cashflow_statement(periods=periods, period=p, as_dataframe=False)
    else:
        raise ValueError(f"Invalid statement_kind: {statement_kind}")

    if stmt is None:
        return {
            "symbol": symbol.upper(),
            "error": "No company facts statement returned (facts may be unavailable for this issuer).",
            "provider": provider_name,
            "api": "company_facts_entityfacts",
        }

    if line_label and line_label.strip():
        needle = line_label.strip()
        finder = getattr(stmt, "find_item", None)
        item = None
        if callable(finder):
            item = finder(label=needle) or finder(concept=needle)
        if item is None:
            return {
                "symbol": symbol.upper(),
                "statement_kind": sk,
                "periods_requested": periods,
                "period": p,
                "error": f"No line matching label/concept '{needle}'.",
                "hint": "Omit line_label to return the full statement tree, or adjust the label.",
                "provider": provider_name,
                "api": "company_facts_entityfacts",
            }
        values = getattr(item, "values", {}) or {}
        return {
            "symbol": symbol.upper(),
            "statement_kind": sk,
            "period": p,
            "line": {
                "label": getattr(item, "label", None),
                "concept": getattr(item, "concept", None),
                "values": values,
            },
            "provider": provider_name,
            "api": "company_facts_entityfacts",
            "assumptions": [
                "Values are from SEC Company Facts (multi-period); suitable for long trends for one company.",
                "Amounts are numeric (USD for US GAAP filers unless noted in filing).",
            ],
        }

    to_dict = getattr(stmt, "to_dict", None)
    if not callable(to_dict):
        return {
            "symbol": symbol.upper(),
            "error": "Statement object has no to_dict(); try as_dataframe path in a future revision.",
            "provider": provider_name,
        }
    # include_empty=True: statement roots are often abstract headers with no period
    # values; include_empty=False drops those nodes before recursing, which can yield
    # items=[] while metadata.total_items is still > 0 (children never serialized).
    raw = to_dict(include_empty=True)
    if not isinstance(raw, dict):
        raw = {"payload": raw}
    _fill_company_facts_items_from_flat_if_needed(stmt, raw)
    data = _truncate_company_facts_dict(raw, _MAX_COMPANY_FACT_LINE_ITEMS)
    data.setdefault("symbol", symbol.upper())
    data["statement_kind"] = sk
    data["periods_requested"] = periods
    data["period"] = p
    data["provider"] = provider_name
    data["api"] = "company_facts_entityfacts"
    data["assumptions"] = [
        "Uses Company.income_statement() / balance_sheet() / cashflow_statement() over SEC Entity Facts.",
        "Best for multi-year single-company trends; for cross-company comparison prefer get_sec_compare_financials_metrics.",
        "Large trees may be truncated in 'items'; omit line_label only when you need exploration.",
    ]
    return data


def _financial_metric_get(name: str, fin: Any, period_offset: int) -> Any:
    n = name.lower().strip()
    if n == "revenue":
        return fin.get_revenue(period_offset=period_offset)
    if n == "net_income":
        return fin.get_net_income(period_offset=period_offset)
    if n == "operating_income":
        return fin.get_operating_income(period_offset=period_offset)
    if n == "total_assets":
        return fin.get_total_assets(period_offset=period_offset)
    if n == "total_liabilities":
        return fin.get_total_liabilities(period_offset=period_offset)
    if n in ("stockholders_equity", "shareholders_equity"):
        return fin.get_stockholders_equity(period_offset=period_offset)
    if n == "operating_cash_flow":
        return fin.get_operating_cash_flow(period_offset=period_offset)
    if n == "free_cash_flow":
        return fin.get_free_cash_flow(period_offset=period_offset)
    if n == "current_assets":
        return fin.get_current_assets(period_offset=period_offset)
    if n == "current_liabilities":
        return fin.get_current_liabilities(period_offset=period_offset)
    raise ValueError(f"Unknown metric: {name}")


def _compare_financials_sync(
    *,
    company_fn: Callable[[str], Any],
    symbols: list[str],
    metrics: list[str],
    period_offsets: list[int],
    provider_name: str,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for sym in symbols:
        sym_u = str(sym).strip().upper()
        co = company_fn(sym_u)
        fin = co.get_financials()
        row: dict[str, Any] = {"symbol": sym_u}
        for m in metrics:
            for off in period_offsets:
                key = f"{m}_period_offset_{off}"
                try:
                    row[key] = _financial_metric_get(m, fin, off)
                except Exception as ex:
                    row[key] = None
                    row[f"{key}_error"] = str(ex)
        rows.append(row)
    return {
        "symbols": [str(s).strip().upper() for s in symbols],
        "metrics": metrics,
        "period_offsets": period_offsets,
        "rows": rows,
        "provider": provider_name,
        "api": "get_financials",
        "assumptions": [
            "Uses Financials API (get_financials()) for apples-to-apples standardized labels across tickers.",
            "Values are whole USD where applicable; getters may be None — never divide without checks.",
            "Not for segment/dimension data; use XBRL tool for segments.",
        ],
    }


def _xbrl_statement_sync(
    *,
    co: Any,
    symbol: str,
    form: str,
    statement: str,
    view: str,
    max_rows: int,
    provider_name: str,
) -> dict[str, Any]:
    ft = str(form).strip().upper()
    try:
        latest = co.get_filings(form=ft).latest(1)
    except Exception as ex:
        return {
            "symbol": symbol.upper(),
            "form": ft,
            "error": f"No filing available: {ex}",
            "provider": provider_name,
        }
    if latest is None:
        return {
            "symbol": symbol.upper(),
            "form": ft,
            "error": f"No {ft} filing found.",
            "provider": provider_name,
        }
    filing = latest
    xbrl = filing.xbrl()
    if xbrl is None:
        return {
            "symbol": symbol.upper(),
            "form": ft,
            "error": "No XBRL in this filing (filing.xbrl() is None).",
            "provider": provider_name,
            "api": "filing_xbrl",
        }
    stmts = xbrl.statements
    st = statement.lower().strip()
    vw = view.lower().strip()
    # Single-filing Statements API: use view= ('detailed' = dimensional / segment rows when present).
    if st == "income":
        stmt = stmts.income_statement(view=vw)
    elif st == "balance_sheet":
        stmt = stmts.balance_sheet(view=vw)
    elif st in ("cash_flow", "cashflow"):
        stmt = stmts.cashflow_statement(view=vw)
    else:
        raise ValueError("statement must be income, balance_sheet, or cash_flow")
    if stmt is None:
        return {
            "symbol": symbol.upper(),
            "form": ft,
            "error": "Requested statement not available in XBRL.",
            "provider": provider_name,
            "api": "filing_xbrl",
        }
    to_df = getattr(stmt, "to_dataframe", None)
    if not callable(to_df):
        return {
            "symbol": symbol.upper(),
            "error": "Statement has no to_dataframe().",
            "provider": provider_name,
        }
    try:
        df = to_df(view=vw)
    except TypeError:
        df = to_df()
    if df is None or getattr(df, "empty", True):
        return {
            "symbol": symbol.upper(),
            "form": ft,
            "columns": [],
            "data": [],
            "note": "Empty dataframe from XBRL statement.",
            "provider": provider_name,
            "api": "filing_xbrl",
        }
    df = df.where(pd.notna(df), None)
    cap = max(10, min(max_rows, _MAX_XBRL_TABLE_ROWS))
    truncated = len(df) > cap
    df = df.head(cap)
    return {
        "symbol": symbol.upper(),
        "form": ft,
        "accession_number": getattr(filing, "accession_number", None),
        "filing_date": str(getattr(filing, "filing_date", "")),
        "statement": st,
        "view": vw,
        "columns": [str(c) for c in df.columns],
        "data": df.to_dict(orient="records"),
        "row_count": len(df),
        "truncated": truncated,
        "provider": provider_name,
        "api": "filing_xbrl",
        "assumptions": [
            "XBRL from a single filing; use view='detailed' for dimensional/segment rows when available.",
            "Slower than Company Facts or Financials; use for segments or custom XBRL lines.",
        ],
    }


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


def _fund_cik_str(cik: Any) -> str | None:
    if cik is None:
        return None
    s = str(cik).strip()
    if not s:
        return None
    digits = "".join(c for c in s if c.isdigit())
    if not digits:
        return s
    try:
        return str(int(digits)).zfill(10)
    except ValueError:
        return s


def _fund_entity_core_dict(fund: Any) -> dict[str, Any]:
    comp = fund.company
    ser = fund.series
    sc = getattr(fund, "share_class", None)
    return {
        "resolved_name": getattr(fund, "name", None),
        "ticker": getattr(fund, "ticker", None),
        "identifier": getattr(fund, "identifier", None),
        "company": {
            "cik": _fund_cik_str(getattr(comp, "cik", None)),
            "name": getattr(comp, "name", None),
        },
        "series": {
            "series_id": getattr(ser, "series_id", None),
            "name": getattr(ser, "name", None),
        },
        "share_class": (
            None
            if sc is None
            else {
                "class_id": getattr(sc, "class_id", None),
                "ticker": getattr(sc, "ticker", None),
                "name": getattr(sc, "name", None),
            }
        ),
    }


def _fund_series_item_to_dict(s: Any) -> dict[str, Any]:
    return {
        "series_id": getattr(s, "series_id", None),
        "name": getattr(s, "name", None),
    }


def _fund_class_item_to_dict(c: Any) -> dict[str, Any]:
    return {
        "class_id": getattr(c, "class_id", None),
        "ticker": getattr(c, "ticker", None),
        "name": getattr(c, "name", None),
    }


def _sec_fund_entity_sync(
    identifier: str,
    *,
    include_series_for_company: bool,
    include_classes_for_series: bool,
    max_series: int,
    max_classes: int,
    provider_name: str,
) -> dict[str, Any]:
    fund = Fund(str(identifier).strip())
    out: dict[str, Any] = {
        **_fund_entity_core_dict(fund),
        "provider": provider_name,
        "api": "edgar.Fund",
        "assumptions": [
            "Identifier may be mutual fund ticker, ETF ticker, series id (S…), or investment company CIK.",
            "Hierarchy is Company > Series > Share Class; ticker applies to share classes when present.",
        ],
    }
    if include_series_for_company:
        rows: list[dict[str, Any]] = []
        for i, s in enumerate(fund.list_series()):
            if i >= max_series:
                break
            rows.append(_fund_series_item_to_dict(s))
        out["series_in_company"] = rows
        out["series_in_company_truncated"] = len(rows) >= max_series
    if include_classes_for_series:
        rows_c: list[dict[str, Any]] = []
        for i, c in enumerate(fund.list_classes()):
            if i >= max_classes:
                break
            rows_c.append(_fund_class_item_to_dict(c))
        out["classes_in_series"] = rows_c
        out["classes_in_series_truncated"] = len(rows_c) >= max_classes
    return out


def _sec_find_funds_sync(
    query: str,
    search_type: str,
    limit: int,
    provider_name: str,
) -> dict[str, Any]:
    st = (search_type or "series").strip().lower()
    if st not in ("series", "company", "class"):
        return {
            "error": f"search_type must be 'series', 'company', or 'class', got {search_type!r}",
            "provider": provider_name,
        }
    recs = find_funds(str(query).strip(), search_type=st)
    lim = max(1, min(limit, _MAX_FUND_SEARCH_RESULTS))
    capped = recs[:lim]
    records: list[dict[str, Any]] = []
    for r in capped:
        # is_dataclass is True for classes and instances; asdict() accepts instances only.
        if is_dataclass(r) and not isinstance(r, type):
            records.append(asdict(r))
        else:
            records.append({"repr": repr(r)})
    return {
        "query": str(query).strip(),
        "search_type": st,
        "match_count": len(recs),
        "returned": len(records),
        "records": records,
        "provider": provider_name,
        "assumptions": [
            "Pass series_id, class_id, ticker, or CIK from a record to get_sec_fund_entity.",
        ],
    }


def _entity_filings_to_rows(filings: Any, limit: int) -> list[dict[str, Any]]:
    n = len(filings)
    cap = max(1, min(limit, _MAX_FUND_FILINGS_RETURN))
    rows: list[dict[str, Any]] = []
    for i in range(min(n, cap)):
        f = filings[i]
        cik = getattr(f, "cik", None)
        rows.append(
            {
                "form": getattr(f, "form", None),
                "filing_date": str(getattr(f, "filing_date", "") or ""),
                "accession_number": getattr(f, "accession_number", None),
                "cik": _fund_cik_str(cik) if cik is not None else None,
                "filing_url": getattr(f, "filing_url", None) or getattr(f, "homepage_url", None),
                "provider": "edgartools",
            }
        )
    return rows


def _sec_fund_filings_sync(
    identifier: str,
    form: str,
    series_only: bool,
    limit: int,
    provider_name: str,
) -> dict[str, Any]:
    fund = Fund(str(identifier).strip())
    ft = str(form or "NPORT-P").strip().upper()
    filings = fund.get_filings(form=ft, series_only=bool(series_only))
    rows = _entity_filings_to_rows(filings, limit)
    return {
        "identifier": str(identifier).strip(),
        "form": ft,
        "series_only": bool(series_only),
        "filing_count_reported": len(filings),
        "filings": rows,
        "provider": provider_name,
        "api": "Fund.get_filings",
        "assumptions": [
            "series_only=True uses EFTS search to narrow filings to those mentioning this fund's series.",
            "Default form NPORT-P is portfolio disclosure for registered funds and ETFs.",
        ],
    }


def _sec_fund_portfolio_sync(identifier: str, max_rows: int, provider_name: str) -> dict[str, Any]:
    fund = Fund(str(identifier).strip())
    df = fund.get_portfolio()
    cap = max(10, min(max_rows, _MAX_FUND_PORTFOLIO_ROWS))
    rows, truncated, omitted = _df_to_records_capped(df, cap)
    n = 0 if df is None or getattr(df, "empty", True) else len(df)
    return {
        "identifier": str(identifier).strip(),
        "holdings": rows,
        "row_count": n,
        "truncated": truncated,
        "rows_omitted": omitted,
        "provider": provider_name,
        "api": "Fund.get_portfolio",
        "assumptions": [
            "Holdings come from the latest NPORT-P disclosure chain via edgartools.",
            "value_usd and pct_value are as reported in the filing extract.",
        ],
    }


def _fund_general_info_to_dict(gi: Any) -> dict[str, Any]:
    if gi is None:
        return {}
    keys = (
        "name",
        "cik",
        "file_number",
        "reg_lei",
        "street1",
        "street2",
        "city",
        "state",
        "country",
        "zip_or_postal_code",
        "phone",
        "series_name",
        "series_lei",
        "series_id",
        "fiscal_year_end",
        "rep_period_date",
        "is_final_filing",
    )
    out: dict[str, Any] = {}
    for k in keys:
        if hasattr(gi, k):
            v = getattr(gi, k)
            if isinstance(v, bool):
                out[k] = v
            elif v is None:
                out[k] = None
            elif isinstance(v, (int, float)):
                out[k] = v
            else:
                out[k] = str(v)
    return out


def _sec_fund_latest_report_sync(
    identifier: str,
    form: str | None,
    max_investment_rows: int,
    provider_name: str,
) -> dict[str, Any]:
    fund = Fund(str(identifier).strip())
    if form and str(form).strip():
        rep = fund.get_latest_report(form=str(form).strip().upper())
    else:
        rep = fund.get_latest_report()
    if rep is None:
        return {"error": "No report returned for this fund and form.", "provider": provider_name}
    filing = getattr(rep, "filing", None)
    gen = _fund_general_info_to_dict(getattr(rep, "general_info", None))
    inv_df = None
    try:
        inv_df = rep.investment_data()
    except Exception as e:
        logger.warning("fund report investment_data failed", error=str(e))
    cap = max(5, min(max_investment_rows, 200))
    rows, truncated, omitted = _df_to_records_capped(inv_df, cap)
    acc = getattr(filing, "accession_number", None) if filing is not None else None
    fd = str(getattr(filing, "filing_date", "") or "") if filing is not None else None
    fm = getattr(filing, "form", None) if filing is not None else None
    return {
        "identifier": str(identifier).strip(),
        "general_info": gen,
        "filing": {
            "accession_number": acc,
            "filing_date": fd,
            "form": fm,
        },
        "investments_sample": rows,
        "investments_truncated": truncated,
        "investments_rows_omitted": omitted,
        "provider": provider_name,
        "api": "Fund.get_latest_report",
        "assumptions": [
            "investments_sample is a capped slice of investment_data() from the parsed report.",
            "For full holdings use get_sec_fund_portfolio when appropriate.",
        ],
    }


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

    @override
    async def is_available(self) -> bool:
        try:
            if _resolve_identity(self._explicit_identity) is None:
                return False
            self._ensure_identity()
            return True
        except Exception as e:
            logger.warning("edgartools availability check failed", error=str(e))
            return False

    @override
    def get_provider_name(self) -> str:
        return self._provider_name

    @staticmethod
    async def _call(fn: Any, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(fn, *args, **kwargs)

    def _company(self, symbol: str) -> Any:
        self._ensure_identity()
        key = _cik_for_company(symbol)
        return Company(key)

    @override
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
            stmt = _statement_from_financials(fin, statement_type)
            columns, records = _statement_to_records(stmt)
            api = "get_financials" if period == "annual" else "get_quarterly_financials"
            return {
                "symbol": symbol.upper(),
                "statement_type": statement_type,
                "period": period,
                "columns": columns,
                "data": records,
                "provider": self._provider_name,
                "edgartools_api": api,
                "assumptions": [
                    "Statement grids come from edgartools Financials API (not raw XBRL on the filing).",
                    "Numeric amounts are reported in whole currency units (USD for US issuers), not thousands.",
                    "Quick getters such as get_revenue() may be None; avoid dividing without a guard.",
                ],
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

    @override
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
        """Download filing body (extension used by agent tools; not on the abstract port).

        Returns raw ``text()`` / ``html()`` for agents. For structured items (e.g. 10-K ``Item 1A``),
        edgartools uses ``filing.obj()`` on the filing object — not exposed here.
        """

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

    @override
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

    @override
    async def get_esg_metrics(self, symbol: str) -> dict[str, Any]:
        logger.warning("edgartools does not provide ESG metrics bundle", symbol=symbol)
        return {"error": "ESG metrics not available from edgartools", "symbol": symbol.upper()}

    @override
    async def get_insider_trading(
        self,
        symbol: str,
        lookback_days: int = 90,
    ) -> list[dict[str, Any]]:
        def _fetch() -> list[dict[str, Any]]:
            co = self._company(symbol)
            head_n = _insider_fetch_head_size(lookback_days)
            form4s = co.get_filings(form="4").head(head_n)
            cutoff = (datetime.now(UTC) - timedelta(days=max(1, lookback_days))).date()
            out: list[dict[str, Any]] = []
            for i in range(len(form4s)):
                filing = form4s[i]
                fd = _filing_date_to_date(getattr(filing, "filing_date", None))
                if fd is not None and fd < cutoff:
                    continue
                row: dict[str, Any] = {
                    "symbol": symbol.upper(),
                    "form": filing.form,
                    "filing_date": str(filing.filing_date),
                    "accession_number": filing.accession_number,
                    "provider": self._provider_name,
                }
                try:
                    obj = filing.obj()
                    summary_fn = getattr(obj, "get_ownership_summary", None)
                    if callable(summary_fn):
                        summary = summary_fn()
                        row["ownership_summary"] = _serialize_ownership_summary(summary)
                    if hasattr(obj, "to_dataframe"):
                        df = obj.to_dataframe()
                        if df is not None and not df.empty:
                            recs = df.fillna("").to_dict(orient="records")
                            cap = _MAX_INSIDER_TX_ROWS_PER_FILING
                            if len(recs) > cap:
                                row["transactions"] = recs[:cap]
                                row["transactions_truncated"] = True
                                row["transactions_omitted_count"] = len(recs) - cap
                            else:
                                row["transactions"] = recs
                except Exception as ex:
                    row["parse_note"] = str(ex)
                if i == 0:
                    row["edgar_form4_notes"] = [
                        "Structured summary is in ownership_summary (use before raw transactions).",
                        "Transaction codes: P=open market purchase, S=sale, A=award, M=option exercise, F=tax withholding.",
                    ]
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

    @override
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
            meta: dict[str, str] = {
                "note": (
                    "Minimal EDGAR snapshot from edgartools. For full statement grids use "
                    "get_financial_statements (Financials API). For 4+ years of single-company "
                    "trends, edgartools recommends get_facts() — not yet mapped into StockFundamentals. "
                    "For ratio-heavy workflows use YFinanceFundamentalProvider."
                ),
                "periods_requested": str(periods),
                "period_type": period_type,
                "amounts_unit": "USD whole dollars for Financials API quick metrics when present",
            }
            try:
                fin = (
                    co.get_financials()
                    if period_type == "annual"
                    else co.get_quarterly_financials()
                )
                rev = fin.get_revenue(period_offset=0)
                ni = fin.get_net_income(period_offset=0)
                if rev is not None:
                    meta["revenue_recent_usd"] = str(rev)
                if ni is not None:
                    meta["net_income_recent_usd"] = str(ni)
                oi = fin.get_operating_income(period_offset=0)
                if oi is not None:
                    meta["operating_income_recent_usd"] = str(oi)
            except Exception as ex:
                meta["financials_quick_metrics_error"] = str(ex)
            return _stock_fundamentals_minimal(
                symbol=symbol.upper(),
                company_name=name,
                provider=self._provider_name,
                data_as_of=datetime.now(UTC),
                metadata=meta,
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

    async def get_sec_company_facts_statement(
        self,
        symbol: str,
        statement_kind: str = "income_statement",
        periods: int = 5,
        period: str = "annual",
        line_label: str | None = None,
    ) -> dict[str, Any]:
        """Multi-period statement from SEC Company Facts (EntityFacts). Best for long history *one* company."""

        if periods < 1 or periods > 12:
            raise ValueError("periods must be between 1 and 12")
        sk = statement_kind.strip().lower()
        if sk in ("cash_flow", "cashflow"):
            sk = "cashflow_statement"

        def _fetch() -> dict[str, Any]:
            co = self._company(symbol)
            return _company_facts_statement_sync(
                co=co,
                symbol=symbol,
                statement_kind=sk,
                periods=periods,
                period=period,
                line_label=line_label,
                provider_name=self._provider_name,
            )

        key_kwargs: dict[str, Any] = {
            "symbol": symbol.upper(),
            "statement_kind": sk,
            "periods": periods,
            "period": period.lower(),
            "line_label": (line_label or "").strip(),
            # Bump when serialization changes so stale empty-item caches are not reused.
            "facts_items_payload": "v2_include_empty_and_flat_fallback",
        }
        return cast(
            dict[str, Any],
            await self._cached_edgar(
                "get_sec_company_facts_statement",
                _TTL_COMPANY_FACTS,
                key_kwargs,
                _fetch,
            ),
        )

    async def get_sec_compare_financials_metrics(
        self,
        symbols: list[str],
        metrics: list[str] | None = None,
        period_offsets: list[int] | None = None,
    ) -> dict[str, Any]:
        """Standardized metrics from ``get_financials()`` for cross-company comparison."""

        if not symbols:
            raise ValueError("symbols must not be empty")
        if len(symbols) > 8:
            raise ValueError("At most 8 symbols per call")
        use_metrics = metrics or ["revenue", "net_income"]
        offs = period_offsets if period_offsets is not None else [0, 1, 2]
        if len(offs) > 5:
            raise ValueError("At most 5 period offsets")

        def _fetch() -> dict[str, Any]:
            return _compare_financials_sync(
                company_fn=lambda s: self._company(s),
                symbols=symbols,
                metrics=use_metrics,
                period_offsets=offs,
                provider_name=self._provider_name,
            )

        key_kwargs = {
            "symbols": [str(s).strip().upper() for s in symbols],
            "metrics": list(use_metrics),
            "period_offsets": list(offs),
        }
        return cast(
            dict[str, Any],
            await self._cached_edgar(
                "get_sec_compare_financials_metrics",
                _TTL_COMPARE_FINANCIALS,
                key_kwargs,
                _fetch,
            ),
        )

    async def get_sec_xbrl_statement_table(
        self,
        symbol: str,
        form: str = "10-K",
        statement: str = "income",
        view: str = "detailed",
        max_rows: int = 300,
    ) -> dict[str, Any]:
        """XBRL statement table from latest filing — use for segments / dimensional data."""

        def _fetch() -> dict[str, Any]:
            co = self._company(symbol)
            return _xbrl_statement_sync(
                co=co,
                symbol=symbol,
                form=form,
                statement=statement,
                view=view,
                max_rows=max_rows,
                provider_name=self._provider_name,
            )

        key_kwargs = {
            "symbol": symbol.upper(),
            "form": str(form).strip().upper(),
            "statement": statement.strip().lower(),
            "view": view.strip().lower(),
            "max_rows": max_rows,
        }
        return cast(
            dict[str, Any],
            await self._cached_edgar(
                "get_sec_xbrl_statement_table",
                _TTL_XBRL_STATEMENT,
                key_kwargs,
                _fetch,
            ),
        )

    async def get_sec_company_edgar_profile(self, symbol: str) -> dict[str, Any]:
        """Entity metadata from EDGAR (name, CIK, SIC, float, shares outstanding)."""

        def _fetch() -> dict[str, Any]:
            co = self._company(symbol)
            return _sec_company_edgar_profile_sync(co, symbol, self._provider_name)

        key_kwargs = {"symbol": str(symbol).strip().upper()}
        return cast(
            dict[str, Any],
            await self._cached_edgar(
                "get_sec_company_edgar_profile",
                _TTL_EDGAR_COMPANY_PROFILE,
                key_kwargs,
                _fetch,
            ),
        )

    async def get_sec_13f_institutional_holdings(
        self,
        filer_symbol_or_cik: str,
        max_holdings_rows: int = 400,
        include_holdings_comparison: bool = False,
        holding_history_periods: int = 0,
    ) -> dict[str, Any]:
        """Latest 13F-HR holdings for an institutional *filer* (manager), not “who holds ticker X”."""

        if max_holdings_rows < 10 or max_holdings_rows > 2000:
            raise ValueError("max_holdings_rows must be between 10 and 2000")
        if holding_history_periods < 0 or holding_history_periods > 4:
            raise ValueError("holding_history_periods must be 0–4")

        def _fetch() -> dict[str, Any]:
            co = self._company(filer_symbol_or_cik)
            return _sec_13f_holdings_sync(
                co,
                max_holdings_rows=max_holdings_rows,
                include_holdings_comparison=include_holdings_comparison,
                holding_history_periods=holding_history_periods,
                provider_name=self._provider_name,
            )

        key_kwargs = {
            "filer": str(filer_symbol_or_cik).strip(),
            "max_holdings_rows": max_holdings_rows,
            "include_holdings_comparison": include_holdings_comparison,
            "holding_history_periods": holding_history_periods,
        }
        return cast(
            dict[str, Any],
            await self._cached_edgar(
                "get_sec_13f_institutional_holdings",
                _TTL_13F_HOLDINGS,
                key_kwargs,
                _fetch,
            ),
        )

    async def get_sec_fund_entity(
        self,
        identifier: str,
        *,
        include_series_for_company: bool = False,
        include_classes_for_series: bool = False,
        max_series: int = 200,
        max_classes: int = 100,
    ) -> dict[str, Any]:
        """Resolve ``edgar.Fund`` — company, series, share class; optional series/class lists."""

        def _fetch() -> dict[str, Any]:
            self._ensure_identity()
            ms = max(1, min(int(max_series), _MAX_FUND_SERIES_LIST))
            mc = max(1, min(int(max_classes), _MAX_FUND_CLASSES_LIST))
            return _sec_fund_entity_sync(
                identifier,
                include_series_for_company=include_series_for_company,
                include_classes_for_series=include_classes_for_series,
                max_series=ms,
                max_classes=mc,
                provider_name=self._provider_name,
            )

        key_kwargs = {
            "identifier": str(identifier).strip(),
            "include_series_for_company": include_series_for_company,
            "include_classes_for_series": include_classes_for_series,
            "max_series": max_series,
            "max_classes": max_classes,
        }
        return cast(
            dict[str, Any],
            await self._cached_edgar(
                "get_sec_fund_entity",
                _TTL_FUND_ENTITY,
                key_kwargs,
                _fetch,
            ),
        )

    async def find_sec_funds(
        self,
        query: str,
        search_type: str = "series",
        limit: int = 40,
    ) -> dict[str, Any]:
        """Search mutual funds / ETFs by name fragment (``find_funds``)."""

        def _fetch() -> dict[str, Any]:
            self._ensure_identity()
            lim = max(1, min(int(limit), _MAX_FUND_SEARCH_RESULTS))
            return _sec_find_funds_sync(query, search_type, lim, self._provider_name)

        key_kwargs = {
            "query": str(query).strip(),
            "search_type": (search_type or "series").strip().lower(),
            "limit": limit,
        }
        return cast(
            dict[str, Any],
            await self._cached_edgar(
                "find_sec_funds",
                _TTL_FUND_SEARCH,
                key_kwargs,
                _fetch,
            ),
        )

    async def get_sec_fund_filings(
        self,
        identifier: str,
        form: str = "NPORT-P",
        series_only: bool = False,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Filings for a fund entity (company-level or ``series_only`` EFTS filter)."""

        def _fetch() -> dict[str, Any]:
            self._ensure_identity()
            lim = max(1, min(int(limit), _MAX_FUND_FILINGS_RETURN))
            return _sec_fund_filings_sync(
                identifier,
                form,
                series_only,
                lim,
                self._provider_name,
            )

        key_kwargs = {
            "identifier": str(identifier).strip(),
            "form": str(form or "NPORT-P").strip().upper(),
            "series_only": bool(series_only),
            "limit": limit,
        }
        return cast(
            dict[str, Any],
            await self._cached_edgar(
                "get_sec_fund_filings",
                _TTL_FUND_FILINGS,
                key_kwargs,
                _fetch,
            ),
        )

    async def get_sec_fund_portfolio(
        self,
        identifier: str,
        max_rows: int = 150,
    ) -> dict[str, Any]:
        """Latest portfolio holdings (``Fund.get_portfolio()`` → NPORT chain)."""

        def _fetch() -> dict[str, Any]:
            self._ensure_identity()
            mr = max(10, min(int(max_rows), _MAX_FUND_PORTFOLIO_ROWS))
            return _sec_fund_portfolio_sync(identifier, mr, self._provider_name)

        key_kwargs = {"identifier": str(identifier).strip(), "max_rows": max_rows}
        return cast(
            dict[str, Any],
            await self._cached_edgar(
                "get_sec_fund_portfolio",
                _TTL_FUND_PORTFOLIO,
                key_kwargs,
                _fetch,
            ),
        )

    async def get_sec_fund_latest_report(
        self,
        identifier: str,
        form: str | None = None,
        max_investment_rows: int = 40,
    ) -> dict[str, Any]:
        """Parsed latest report (default NPORT-P) with general info + capped investment rows."""

        def _fetch() -> dict[str, Any]:
            self._ensure_identity()
            mir = max(5, min(int(max_investment_rows), 200))
            return _sec_fund_latest_report_sync(identifier, form, mir, self._provider_name)

        key_kwargs = {
            "identifier": str(identifier).strip(),
            "form": (form.strip().upper() if isinstance(form, str) and form.strip() else None),
            "max_investment_rows": max_investment_rows,
        }
        return cast(
            dict[str, Any],
            await self._cached_edgar(
                "get_sec_fund_latest_report",
                _TTL_FUND_REPORT,
                key_kwargs,
                _fetch,
            ),
        )
