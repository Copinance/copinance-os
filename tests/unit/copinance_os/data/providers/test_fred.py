"""Unit tests for FRED macroeconomic provider."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from copinance_os.data.providers.fred import FredMacroeconomicProvider


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

    @pytest.mark.asyncio
    async def test_get_release_dates_chains_series_release_and_release_dates(self) -> None:
        provider = FredMacroeconomicProvider(api_key="test-key", base_url="https://example.com")

        calls: list[tuple[str, dict[str, object]]] = []

        class DummyClient:
            async def get(
                self, path: str, params: dict, timeout: float | None = None
            ) -> httpx.Response:
                calls.append((path, dict(params)))
                if path == "/series/release":
                    payload = {"releases": [{"id": 82, "name": "Employment Situation"}]}
                elif path == "/release/dates":
                    payload = {
                        "release_dates": [
                            {"release_id": 82, "date": "2025-01-03"},
                            {"release_id": 82, "date": "2025-01-10"},
                        ]
                    }
                else:
                    raise AssertionError(f"unexpected path {path}")
                req = httpx.Request("GET", f"https://example.com{path}")
                return httpx.Response(200, json=payload, request=req)

        async def _dummy_get_client() -> DummyClient:  # type: ignore[override]
            return DummyClient()

        provider._get_client = _dummy_get_client  # type: ignore[method-assign]

        dates = await provider.get_release_dates("UNRATE", limit=50)

        assert calls[0][0] == "/series/release"
        assert calls[0][1]["series_id"] == "UNRATE"
        assert calls[1][0] == "/release/dates"
        assert calls[1][1]["release_id"] == 82
        assert calls[1][1]["limit"] == 50
        assert calls[1][1]["sort_order"] == "desc"
        assert dates == [
            datetime(2025, 1, 3, tzinfo=UTC),
            datetime(2025, 1, 10, tzinfo=UTC),
        ]

    @pytest.mark.asyncio
    async def test_get_release_dates_accepts_singular_release_payload(self) -> None:
        provider = FredMacroeconomicProvider(api_key="test-key", base_url="https://example.com")

        class DummyClient:
            def __init__(self) -> None:
                self._step = 0

            async def get(
                self, path: str, params: dict, timeout: float | None = None
            ) -> httpx.Response:
                self._step += 1
                if path == "/series/release":
                    payload = {"release": {"id": 10, "name": "GDP"}}
                else:
                    payload = {"release_dates": [{"release_id": 10, "date": "2024-06-01"}]}
                req = httpx.Request("GET", f"https://example.com{path}")
                return httpx.Response(200, json=payload, request=req)

        async def _dummy_get_client() -> DummyClient:  # type: ignore[override]
            return DummyClient()

        provider._get_client = _dummy_get_client  # type: ignore[method-assign]

        dates = await provider.get_release_dates("GNPCA")
        assert dates == [datetime(2024, 6, 1, tzinfo=UTC)]

    @pytest.mark.asyncio
    async def test_get_release_dates_empty_when_no_release(self) -> None:
        provider = FredMacroeconomicProvider(api_key="test-key", base_url="https://example.com")

        class DummyClient:
            async def get(
                self, path: str, params: dict, timeout: float | None = None
            ) -> httpx.Response:
                payload: dict[str, object] = {"releases": []} if path == "/series/release" else {}
                req = httpx.Request("GET", f"https://example.com{path}")
                return httpx.Response(200, json=payload, request=req)

        async def _dummy_get_client() -> DummyClient:  # type: ignore[override]
            return DummyClient()

        provider._get_client = _dummy_get_client  # type: ignore[method-assign]

        dates = await provider.get_release_dates("UNKNOWN")
        assert dates == []

    @pytest.mark.asyncio
    async def test_get_release_dates_requires_api_key(self) -> None:
        provider = FredMacroeconomicProvider(api_key=None)
        with pytest.raises(RuntimeError):
            await provider.get_release_dates("UNRATE")

    @pytest.mark.asyncio
    async def test_get_release_dates_retries_transient_transport_error(self, monkeypatch) -> None:
        provider = FredMacroeconomicProvider(api_key="test-key", base_url="https://example.com")
        provider._retry_base_delay_seconds = 0.0
        provider._retry_max_delay_seconds = 0.0

        attempts = {"series_release": 0}

        class DummyClient:
            async def get(
                self, path: str, params: dict, timeout: float | None = None
            ) -> httpx.Response:
                if path == "/series/release":
                    attempts["series_release"] += 1
                    if attempts["series_release"] == 1:
                        req = httpx.Request("GET", "https://example.com/series/release")
                        raise httpx.ConnectError("transient network drop", request=req)
                    payload = {"releases": [{"id": 50, "name": "Employment Situation"}]}
                elif path == "/release/dates":
                    payload = {
                        "release_dates": [
                            {"release_id": 50, "date": "2026-04-03"},
                            {"release_id": 50, "date": "2026-03-06"},
                        ]
                    }
                else:
                    raise AssertionError(f"unexpected path {path}")
                req = httpx.Request("GET", f"https://example.com{path}")
                return httpx.Response(200, json=payload, request=req)

        async def _dummy_get_client() -> DummyClient:  # type: ignore[override]
            return DummyClient()

        provider._get_client = _dummy_get_client  # type: ignore[method-assign]
        monkeypatch.setattr("copinance_os.data.providers.fred.random.uniform", lambda _a, _b: 0.0)

        dates = await provider.get_release_dates("UNRATE", limit=2)

        assert attempts["series_release"] == 2
        assert dates == [
            datetime(2026, 4, 3, tzinfo=UTC),
            datetime(2026, 3, 6, tzinfo=UTC),
        ]

    @pytest.mark.asyncio
    async def test_get_release_dates_raises_after_retry_exhaustion(self, monkeypatch) -> None:
        provider = FredMacroeconomicProvider(api_key="test-key", base_url="https://example.com")
        provider._retry_base_delay_seconds = 0.0
        provider._retry_max_delay_seconds = 0.0
        provider._max_retry_attempts = 2

        class DummyClient:
            async def get(
                self, path: str, params: dict, timeout: float | None = None
            ) -> httpx.Response:
                req = httpx.Request("GET", f"https://example.com{path}")
                raise httpx.RemoteProtocolError("Server disconnected", request=req)

        async def _dummy_get_client() -> DummyClient:  # type: ignore[override]
            return DummyClient()

        provider._get_client = _dummy_get_client  # type: ignore[method-assign]
        monkeypatch.setattr("copinance_os.data.providers.fred.random.uniform", lambda _a, _b: 0.0)

        with pytest.raises(httpx.RemoteProtocolError):
            await provider.get_release_dates("UNRATE")

    @pytest.mark.asyncio
    async def test_get_release_dates_retries_on_http_500_then_succeeds(self, monkeypatch) -> None:
        provider = FredMacroeconomicProvider(api_key="test-key", base_url="https://example.com")
        provider._retry_base_delay_seconds = 0.0
        provider._retry_max_delay_seconds = 0.0

        attempts = {"series_release": 0}

        class DummyClient:
            async def get(
                self, path: str, params: dict, timeout: float | None = None
            ) -> httpx.Response:
                req = httpx.Request("GET", f"https://example.com{path}")
                if path == "/series/release":
                    attempts["series_release"] += 1
                    if attempts["series_release"] == 1:
                        return httpx.Response(500, json={"error": "temporary outage"}, request=req)
                    return httpx.Response(
                        200,
                        json={"releases": [{"id": 50, "name": "Employment Situation"}]},
                        request=req,
                    )
                if path == "/release/dates":
                    return httpx.Response(
                        200,
                        json={"release_dates": [{"release_id": 50, "date": "2026-04-03"}]},
                        request=req,
                    )
                raise AssertionError(f"unexpected path {path}")

        async def _dummy_get_client() -> DummyClient:  # type: ignore[override]
            return DummyClient()

        provider._get_client = _dummy_get_client  # type: ignore[method-assign]
        monkeypatch.setattr("copinance_os.data.providers.fred.random.uniform", lambda _a, _b: 0.0)

        dates = await provider.get_release_dates("UNRATE", limit=1)
        assert attempts["series_release"] == 2
        assert dates == [datetime(2026, 4, 3, tzinfo=UTC)]

    @pytest.mark.asyncio
    async def test_get_release_dates_raises_http_status_after_retry_exhaustion(
        self, monkeypatch
    ) -> None:
        provider = FredMacroeconomicProvider(api_key="test-key", base_url="https://example.com")
        provider._retry_base_delay_seconds = 0.0
        provider._retry_max_delay_seconds = 0.0
        provider._max_retry_attempts = 2

        class DummyClient:
            async def get(
                self, path: str, params: dict, timeout: float | None = None
            ) -> httpx.Response:
                req = httpx.Request("GET", f"https://example.com{path}")
                return httpx.Response(500, json={"error": "still down"}, request=req)

        async def _dummy_get_client() -> DummyClient:  # type: ignore[override]
            return DummyClient()

        provider._get_client = _dummy_get_client  # type: ignore[method-assign]
        monkeypatch.setattr("copinance_os.data.providers.fred.random.uniform", lambda _a, _b: 0.0)

        with pytest.raises(httpx.HTTPStatusError):
            await provider.get_release_dates("UNRATE")

    @pytest.mark.asyncio
    async def test_is_available_uses_client_timeout_not_five_seconds(self) -> None:
        provider = FredMacroeconomicProvider(api_key="test-key", base_url="https://example.com")
        seen_timeout: dict[str, float | None] = {}

        class DummyClient:
            async def get(
                self, path: str, params: dict, timeout: float | None = None
            ) -> httpx.Response:
                seen_timeout["timeout"] = timeout
                req = httpx.Request("GET", f"https://example.com{path}")
                return httpx.Response(200, json={"seriess": [{"id": "DGS10"}]}, request=req)

        async def _dummy_get_client() -> DummyClient:  # type: ignore[override]
            return DummyClient()

        provider._get_client = _dummy_get_client  # type: ignore[method-assign]
        assert await provider.is_available() is True
        assert seen_timeout["timeout"] is None
        assert provider.last_availability_error is None

    @pytest.mark.asyncio
    async def test_is_available_timeout_sets_fred_timeout(self) -> None:
        provider = FredMacroeconomicProvider(api_key="test-key", base_url="https://example.com")
        provider._retry_base_delay_seconds = 0.0
        provider._retry_max_delay_seconds = 0.0
        provider._max_retry_attempts = 1

        class DummyClient:
            async def get(
                self, path: str, params: dict, timeout: float | None = None
            ) -> httpx.Response:
                req = httpx.Request("GET", f"https://example.com{path}")
                raise httpx.ReadTimeout("slow", request=req)

        async def _dummy_get_client() -> DummyClient:  # type: ignore[override]
            return DummyClient()

        provider._get_client = _dummy_get_client  # type: ignore[method-assign]
        assert await provider.is_available() is False
        assert provider.last_availability_error == "fred_timeout"
