"""Unit tests for EdgarTools fundamental provider (mocked edgar SDK)."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from copinance_os.data.providers.sec.edgartools import (
    EdgarToolsFundamentalProvider,
    _filing_date_to_date,
    _fund_cik_str,
    _parse_cik_int,
    _resolve_identity,
    _sec_find_funds_sync,
    _serialize_ownership_summary,
)


@pytest.mark.unit
class TestEdgarToolsHelpers:
    def test_resolve_identity_explicit(self) -> None:
        assert _resolve_identity("  Jane Doe j@x.com  ") == "Jane Doe j@x.com"

    def test_parse_cik_int(self) -> None:
        assert _parse_cik_int("0000320193") == 320193
        assert _parse_cik_int("320193") == 320193

    def test_fund_cik_str(self) -> None:
        assert _fund_cik_str(36405) == "0000036405"
        assert _fund_cik_str("0000884394") == "0000884394"
        assert _fund_cik_str(None) is None

    def test_sec_find_funds_invalid_search_type(self) -> None:
        out = _sec_find_funds_sync("vanguard", "not-a-type", 5, "edgartools")
        assert "error" in out

    def test_filing_date_to_date(self) -> None:
        assert _filing_date_to_date(date(2025, 1, 2)) == date(2025, 1, 2)
        assert _filing_date_to_date(pd.Timestamp("2024-06-15")) == date(2024, 6, 15)

    def test_serialize_ownership_summary_transaction_shape(self) -> None:
        class _TxSummary:
            insider_name = "Jane Doe"
            issuer_name = "Example Inc"
            issuer_ticker = "EXM"
            position = "CEO"
            reporting_date = "2025-01-01"
            form_type = "4"
            remarks = ""

            @property
            def primary_activity(self) -> str:
                return "Purchase"

            @property
            def net_change(self) -> int:
                return 1000

            @property
            def net_value(self) -> float:
                return 50000.0

            @property
            def remaining_shares(self) -> int:
                return 10_000

            @property
            def has_derivative_transactions(self) -> bool:
                return False

            @property
            def transaction_types(self) -> list[str]:
                return ["purchase"]

        d = _serialize_ownership_summary(_TxSummary())
        assert d["primary_activity"] == "Purchase"
        assert d["net_shares_change"] == 1000
        assert d["net_value_usd"] == 50000.0


@pytest.mark.unit
class TestEdgarToolsFundamentalProvider:
    def test_provider_name(self) -> None:
        p = EdgarToolsFundamentalProvider(identity="Test User test@example.com")
        assert p.get_provider_name() == "edgartools"

    @pytest.mark.asyncio
    async def test_is_available_false_without_identity(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            p = EdgarToolsFundamentalProvider(identity=None)
            assert await p.is_available() is False

    @pytest.mark.asyncio
    async def test_get_sec_filings_mocked(self) -> None:
        mock_f = MagicMock()
        mock_f.form = "10-K"
        mock_f.filing_date = "2025-10-31"
        mock_f.accession_number = "0000320193-25-000079"
        mock_f.cik = 320193
        mock_f.filing_url = "https://example.com/f"
        mock_f.homepage_url = None

        mock_batch = MagicMock()
        mock_batch.__len__.return_value = 1
        mock_batch.__getitem__.side_effect = lambda i: mock_f if i == 0 else None

        mock_filings = MagicMock()
        mock_filings.head.return_value = mock_batch

        mock_co = MagicMock()
        mock_co.get_filings.return_value = mock_filings

        # Patch where Company is bound (from edgar import Company — edgar.Company patch is ignored).
        with (
            patch(
                "copinance_os.data.providers.sec.edgartools.Company",
                return_value=mock_co,
            ),
            patch(
                "copinance_os.data.providers.sec.edgartools.EdgarToolsFundamentalProvider._ensure_identity"
            ),
        ):
            p = EdgarToolsFundamentalProvider(identity="T t@t.com")
            out = await p.get_sec_filings("AAPL", ["10-K"], limit=5)
            assert len(out) == 1
            assert out[0]["form"] == "10-K"
            assert out[0]["cik"] == "0000320193"
            assert out[0]["accession_number"] == "0000320193-25-000079"

    @pytest.mark.asyncio
    async def test_get_sec_filing_content_error_when_empty(self) -> None:
        mock_filings = MagicMock()
        mock_filings.__len__.return_value = 0

        mock_co = MagicMock()
        mock_co.get_filings.return_value = mock_filings

        with (
            patch(
                "copinance_os.data.providers.sec.edgartools.Company",
                return_value=mock_co,
            ),
            patch(
                "copinance_os.data.providers.sec.edgartools.EdgarToolsFundamentalProvider._ensure_identity"
            ),
        ):
            p = EdgarToolsFundamentalProvider(identity="T t@t.com")
            res = await p.get_sec_filing_content("0000320193", "missing-acc")
            assert "error" in res

    @pytest.mark.asyncio
    async def test_get_financial_statements_mocked(self) -> None:
        mock_df = pd.DataFrame({"Line": ["Revenues"], "2024": [100.0]})
        mock_stmt = MagicMock()
        mock_stmt.to_dataframe.return_value = mock_df

        mock_fin = MagicMock()
        mock_fin.income_statement.return_value = mock_stmt

        mock_co = MagicMock()
        mock_co.get_financials.return_value = mock_fin

        with (
            patch(
                "copinance_os.data.providers.sec.edgartools.Company",
                return_value=mock_co,
            ),
            patch(
                "copinance_os.data.providers.sec.edgartools.EdgarToolsFundamentalProvider._ensure_identity"
            ),
        ):
            p = EdgarToolsFundamentalProvider(identity="T t@t.com")
            out = await p.get_financial_statements("AAPL", "income_statement", "annual")
            assert out["edgartools_api"] == "get_financials"
            assert "assumptions" in out
            assert out["data"][0]["Line"] == "Revenues"
            mock_co.get_quarterly_financials.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_insider_trading_uses_ownership_summary_mocked(self) -> None:
        recent = date.today()
        old = recent - timedelta(days=400)

        def make_filing(d: date) -> MagicMock:
            f = MagicMock()
            f.form = "4"
            f.filing_date = d
            f.accession_number = f"acc-{d.isoformat()}"
            summary = MagicMock()
            summary.insider_name = "Insider"
            summary.issuer_name = "Co"
            summary.issuer_ticker = "CO"
            summary.position = "Officer"
            summary.reporting_date = str(d)
            summary.form_type = "4"
            summary.remarks = ""
            type(summary).primary_activity = property(lambda self: "Sale")
            type(summary).net_change = property(lambda self: -50)
            type(summary).net_value = property(lambda self: -5000.0)
            type(summary).remaining_shares = property(lambda self: None)
            type(summary).has_derivative_transactions = property(lambda self: False)
            type(summary).transaction_types = property(lambda self: ["sale"])
            obj = MagicMock()
            obj.get_ownership_summary.return_value = summary
            obj.to_dataframe.return_value = pd.DataFrame()
            f.obj.return_value = obj
            return f

        mock_batch = MagicMock()
        mock_batch.__len__.return_value = 2
        mock_batch.__getitem__.side_effect = lambda i: (
            make_filing(recent) if i == 0 else make_filing(old)
        )

        mock_filings = MagicMock()
        mock_filings.head.return_value = mock_batch

        mock_co = MagicMock()
        mock_co.get_filings.return_value = mock_filings

        with (
            patch(
                "copinance_os.data.providers.sec.edgartools.Company",
                return_value=mock_co,
            ),
            patch(
                "copinance_os.data.providers.sec.edgartools.EdgarToolsFundamentalProvider._ensure_identity"
            ),
        ):
            p = EdgarToolsFundamentalProvider(identity="T t@t.com")
            out = await p.get_insider_trading("CO", lookback_days=365)
            assert len(out) == 1
            assert out[0]["ownership_summary"]["insider_name"] == "Insider"
            assert out[0]["ownership_summary"]["primary_activity"] == "Sale"

    @pytest.mark.asyncio
    async def test_get_sec_fund_entity_mocked(self) -> None:
        mock_comp = MagicMock()
        mock_comp.cik = 36405
        mock_comp.name = "VANGUARD INDEX FUNDS"
        mock_ser = MagicMock()
        mock_ser.series_id = "S000002839"
        mock_ser.name = "Vanguard 500 Index Fund"
        mock_f = MagicMock()
        mock_f.name = "Vanguard 500 Index Fund"
        mock_f.ticker = "VFINX"
        mock_f.identifier = "C000007773"
        mock_f.company = mock_comp
        mock_f.series = mock_ser
        mock_f.share_class = MagicMock(class_id="C1", ticker="VFINX", name="Investor")
        mock_f.list_series.return_value = []
        mock_f.list_classes.return_value = []

        with (
            patch(
                "copinance_os.data.providers.sec.edgartools.Fund",
                return_value=mock_f,
            ),
            patch(
                "copinance_os.data.providers.sec.edgartools.EdgarToolsFundamentalProvider._ensure_identity"
            ),
        ):
            p = EdgarToolsFundamentalProvider(identity="T t@t.com")
            out = await p.get_sec_fund_entity("VFINX")
            assert out["ticker"] == "VFINX"
            assert out["company"]["cik"] == "0000036405"
            assert out["series"]["series_id"] == "S000002839"
            assert out["share_class"]["ticker"] == "VFINX"
