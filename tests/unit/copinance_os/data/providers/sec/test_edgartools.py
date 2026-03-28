"""Unit tests for EdgarTools fundamental provider (mocked edgar SDK)."""

from unittest.mock import MagicMock, patch

import pytest

from copinance_os.data.providers.sec.edgartools import (
    EdgarToolsFundamentalProvider,
    _parse_cik_int,
    _resolve_identity,
)


@pytest.mark.unit
class TestEdgarToolsHelpers:
    def test_resolve_identity_explicit(self) -> None:
        assert _resolve_identity("  Jane Doe j@x.com  ") == "Jane Doe j@x.com"

    def test_parse_cik_int(self) -> None:
        assert _parse_cik_int("0000320193") == 320193
        assert _parse_cik_int("320193") == 320193


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
