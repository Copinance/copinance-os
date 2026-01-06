"""Unit tests for FRED macroeconomic provider."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from copinanceos.infrastructure.data_providers.fred import FredMacroeconomicProvider


@pytest.mark.unit
class TestFredMacroeconomicProvider:
    @pytest.mark.asyncio
    async def test_get_time_series_parses_and_skips_missing(self) -> None:
        provider = FredMacroeconomicProvider(api_key="test-key", base_url="https://example.com")

        class DummyClient:
            async def get(
                self, path: str, params: dict, timeout: float | None = None
            ) -> httpx.Response:
                assert path == "/series/observations"
                payload = {
                    "observations": [
                        {"date": "2025-01-01", "value": "4.00"},
                        {"date": "2025-01-02", "value": "."},
                        {"date": "2025-01-03", "value": "4.10"},
                    ]
                }
                req = httpx.Request("GET", "https://example.com/series/observations")
                return httpx.Response(200, json=payload, request=req)

        async def _dummy_get_client() -> DummyClient:  # type: ignore[override]
            return DummyClient()

        provider._get_client = _dummy_get_client  # type: ignore[method-assign]

        points = await provider.get_time_series(
            "DGS10",
            datetime(2025, 1, 1, tzinfo=UTC),
            datetime(2025, 1, 5, tzinfo=UTC),
        )

        assert len(points) == 2
        assert points[0].series_id == "DGS10"
        assert float(points[0].value) == 4.0
        assert float(points[1].value) == 4.1

    @pytest.mark.asyncio
    async def test_get_time_series_requires_api_key(self) -> None:
        provider = FredMacroeconomicProvider(api_key=None)
        with pytest.raises(RuntimeError):
            await provider.get_time_series(
                "DGS10",
                datetime(2025, 1, 1, tzinfo=UTC),
                datetime(2025, 1, 5, tzinfo=UTC),
            )
