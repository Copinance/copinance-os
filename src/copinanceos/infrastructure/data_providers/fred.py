"""FRED (Federal Reserve Economic Data) macroeconomic data provider implementation."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
import structlog

from copinanceos.domain.models.macro import MacroDataPoint
from copinanceos.domain.ports.data_providers import MacroeconomicDataProvider

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

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
