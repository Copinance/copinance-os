"""FRED (Federal Reserve Economic Data) macroeconomic data provider implementation."""

from __future__ import annotations

import asyncio
import random
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

import httpx
import structlog
from typing_extensions import override

from copinance_os.domain.models.market.macro import MacroDataPoint
from copinance_os.domain.ports.data_providers import MacroeconomicDataProvider

logger = structlog.get_logger(__name__)


class FredMacroeconomicProvider(MacroeconomicDataProvider):
    """FRED implementation of MacroeconomicDataProvider."""

    def __init__(
        self,
        api_key: str | None,
        base_url: str = "https://api.stlouisfed.org/fred",
        rate_limit_delay: float = 0.1,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._rate_limit_delay = rate_limit_delay
        self._timeout_seconds = timeout_seconds
        self._client: httpx.AsyncClient | None = None
        self._max_retry_attempts = 3
        self._retry_base_delay_seconds = 0.25
        self._retry_max_delay_seconds = 2.0

    @override
    def get_provider_name(self) -> str:
        return "fred"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout_seconds,
                follow_redirects=True,
            )
        return self._client

    async def _get_with_retry(
        self,
        path: str,
        *,
        params: dict[str, Any],
    ) -> httpx.Response:
        """Execute GET with bounded retries for transient transport failures."""
        client = await self._get_client()
        for attempt in range(1, self._max_retry_attempts + 1):
            try:
                response = await client.get(path, params=params)
                is_transient_status = response.status_code == 429 or response.status_code >= 500
                if is_transient_status and attempt < self._max_retry_attempts:
                    backoff = min(
                        self._retry_max_delay_seconds,
                        self._retry_base_delay_seconds * (2 ** (attempt - 1)),
                    )
                    jitter = random.uniform(0.0, backoff * 0.2)
                    delay = backoff + jitter
                    logger.warning(
                        "Transient FRED HTTP status; retrying request",
                        path=path,
                        attempt=attempt,
                        max_attempts=self._max_retry_attempts,
                        status_code=response.status_code,
                        delay_seconds=round(delay, 3),
                    )
                    await asyncio.sleep(delay)
                    continue
                return response
            except httpx.TransportError as exc:
                if attempt >= self._max_retry_attempts:
                    raise
                backoff = min(
                    self._retry_max_delay_seconds,
                    self._retry_base_delay_seconds * (2 ** (attempt - 1)),
                )
                jitter = random.uniform(0.0, backoff * 0.2)
                delay = backoff + jitter
                logger.warning(
                    "Transient FRED transport error; retrying request",
                    path=path,
                    attempt=attempt,
                    max_attempts=self._max_retry_attempts,
                    delay_seconds=round(delay, 3),
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
                await asyncio.sleep(delay)
        raise RuntimeError("FRED retry loop exhausted without response")

    @override
    async def is_available(self) -> bool:
        if not self._api_key:
            logger.debug("FRED API key not set", has_api_key=False)
            return False
        try:
            client = await self._get_client()
            # Lightweight series metadata call
            resp = await client.get(
                "/series",
                params={"series_id": "DGS10", "api_key": self._api_key, "file_type": "json"},
                timeout=5.0,
            )
            if resp.status_code == 200:
                logger.debug("FRED availability check passed", status_code=resp.status_code)
                return True
            else:
                logger.warning(
                    "FRED availability check failed",
                    status_code=resp.status_code,
                    response_text=resp.text[:200] if resp.text else None,
                )
                return False
        except Exception as e:
            logger.warning(
                "FRED availability check failed with exception",
                error=str(e),
                error_type=type(e).__name__,
            )
            return False

    @override
    async def get_time_series(
        self,
        series_id: str,
        start_date: datetime,
        end_date: datetime,
        *,
        frequency: str | None = None,
    ) -> list[MacroDataPoint]:
        if not self._api_key:
            raise RuntimeError("FRED API key not configured (set COPINANCEOS_FRED_API_KEY)")

        client = await self._get_client()
        params: dict[str, Any] = {
            "series_id": series_id,
            "api_key": self._api_key,
            "file_type": "json",
            "observation_start": start_date.date().isoformat(),
            "observation_end": end_date.date().isoformat(),
        }
        if frequency:
            params["frequency"] = frequency

        await asyncio.sleep(self._rate_limit_delay)
        resp = await client.get("/series/observations", params=params)
        resp.raise_for_status()
        payload = resp.json()

        observations = payload.get("observations", [])
        points: list[MacroDataPoint] = []
        for obs in observations:
            date_str = obs.get("date")
            value_str = obs.get("value")
            if not date_str or not value_str or value_str == ".":
                continue
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC)
                val = Decimal(value_str)
            except (ValueError, InvalidOperation):
                continue

            points.append(
                MacroDataPoint(
                    series_id=series_id,
                    timestamp=dt,
                    value=val,
                    metadata={},
                )
            )

        return points

    async def get_release_dates(
        self,
        series_id: str,
        *,
        limit: int = 1000,
        sort_order: Literal["asc", "desc"] = "desc",
    ) -> list[datetime]:
        """Return scheduled release dates for the FRED release that contains ``series_id``.

        Resolves the series' parent release via ``/series/release``, then fetches
        ``/release/dates`` for that release. When FRED returns multiple releases
        for one series, the first entry is used.

        Args:
            series_id: FRED series identifier (e.g. ``UNRATE``).
            limit: Maximum number of dates to return (passed to the FRED API).
            sort_order: ``asc`` or ``desc`` (newest first when ``desc``).

        Returns:
            Release dates as UTC midnight timestamps, ordered per ``sort_order``.
        """
        if not self._api_key:
            raise RuntimeError("FRED API key not configured (set COPINANCEOS_FRED_API_KEY)")

        base_params: dict[str, Any] = {
            "api_key": self._api_key,
            "file_type": "json",
        }

        await asyncio.sleep(self._rate_limit_delay)
        rel_resp = await self._get_with_retry(
            "/series/release",
            params={**base_params, "series_id": series_id},
        )
        rel_resp.raise_for_status()
        rel_payload = rel_resp.json()

        releases_raw = rel_payload.get("releases")
        if not isinstance(releases_raw, list) or not releases_raw:
            single = rel_payload.get("release")
            if isinstance(single, dict):
                releases_raw = [single]
            else:
                return []

        first = releases_raw[0]
        if not isinstance(first, dict):
            return []
        release_id = first.get("id")
        if release_id is None:
            return []

        await asyncio.sleep(self._rate_limit_delay)
        dates_resp = await self._get_with_retry(
            "/release/dates",
            params={
                **base_params,
                "release_id": release_id,
                "limit": limit,
                "sort_order": sort_order,
            },
        )
        dates_resp.raise_for_status()
        dates_payload = dates_resp.json()

        rows = dates_payload.get("release_dates")
        if not isinstance(rows, list):
            return []

        out: list[datetime] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            date_str = row.get("date")
            if not date_str or not isinstance(date_str, str):
                continue
            try:
                out.append(datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=UTC))
            except ValueError:
                continue

        return out

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
