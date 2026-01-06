"""Macro regime indicators tool (rates, credit, commodities).

Prefers high-quality time series from a MacroeconomicDataProvider (e.g., FRED) and
falls back to yfinance proxies via MarketDataProvider when needed.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog

from copinanceos.domain.models.macro import MacroDataPoint
from copinanceos.domain.models.tool_results import ToolResult
from copinanceos.domain.ports.data_providers import MacroeconomicDataProvider, MarketDataProvider
from copinanceos.domain.ports.tools import Tool, ToolSchema

logger = structlog.get_logger(__name__)


def _last_n(points: list[MacroDataPoint], n: int) -> list[MacroDataPoint]:
    return points[-n:] if len(points) >= n else points


def _safe_decimal(val: float | int | str) -> Decimal:
    return Decimal(str(val))


def _series_metrics(points: list[MacroDataPoint], lookback_points: int = 20) -> dict[str, Any]:
    if not points:
        return {"available": False, "error": "No data points"}

    pts = [p for p in points if p.value is not None]
    if not pts:
        return {"available": False, "error": "No valid values"}

    latest = pts[-1]
    result: dict[str, Any] = {
        "available": True,
        "latest": {"timestamp": latest.timestamp.isoformat(), "value": float(latest.value)},
        "data_points": len(pts),
    }

    if len(pts) > lookback_points:
        prev = pts[-(lookback_points + 1)]
        delta = latest.value - prev.value
        result["change_20d"] = float(delta)

    return result


class MacroRegimeIndicatorsTool(Tool):
    """Tool that returns macro regime indicators (rates, credit, commodities)."""

    def __init__(
        self,
        macro_data_provider: MacroeconomicDataProvider,
        market_data_provider: MarketDataProvider,
    ) -> None:
        self._macro_provider = macro_data_provider
        self._market_provider = market_data_provider

    def get_name(self) -> str:
        return "get_macro_regime_indicators"

    def get_description(self) -> str:
        return (
            "Get macro regime indicators using FRED-quality time series when available "
            "(yields, yield curve, credit spreads, energy) and fall back to market proxies "
            "when FRED is unavailable."
        )

    def get_schema(self) -> ToolSchema:
        return ToolSchema(
            name=self.get_name(),
            description=self.get_description(),
            parameters={
                "type": "object",
                "properties": {
                    "lookback_days": {
                        "type": "integer",
                        "description": "Number of days to analyze (default: 252)",
                        "default": 252,
                    },
                    "include_rates": {
                        "type": "boolean",
                        "description": "Include rates/yield-curve indicators (default: true)",
                        "default": True,
                    },
                    "include_credit": {
                        "type": "boolean",
                        "description": "Include credit spread indicators (default: true)",
                        "default": True,
                    },
                    "include_commodities": {
                        "type": "boolean",
                        "description": "Include commodities/energy indicators (default: true)",
                        "default": True,
                    },
                },
                "required": [],
            },
            returns={
                "type": "object",
                "description": "Macro regime indicators including rates, credit, and commodities.",
            },
        )

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            validated = self.validate_parameters(**kwargs)
            lookback_days = int(validated.get("lookback_days", 252))
            include_rates = bool(validated.get("include_rates", True))
            include_credit = bool(validated.get("include_credit", True))
            include_commodities = bool(validated.get("include_commodities", True))

            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days + 30)

            data: dict[str, Any] = {
                "analysis_date": end_date.isoformat(),
                "lookback_days": lookback_days,
            }

            if include_rates:
                data["rates"] = await self._get_rates_block(start_date, end_date)

            if include_credit:
                data["credit"] = await self._get_credit_block(start_date, end_date)

            if include_commodities:
                data["commodities"] = await self._get_commodities_block(start_date, end_date)

            return ToolResult(success=True, data=data, metadata={"lookback_days": lookback_days})
        except Exception as e:
            logger.error("Failed to get macro regime indicators", error=str(e), exc_info=True)
            return ToolResult(
                success=False,
                data=None,
                error=f"Failed to get macro regime indicators: {str(e)}",
                metadata={"error_type": type(e).__name__},
            )

    async def _get_rates_block(self, start_date: datetime, end_date: datetime) -> dict[str, Any]:
        # Check if FRED is available first
        fred_available = await self._macro_provider.is_available()
        provider_name = self._macro_provider.get_provider_name()

        # Check if API key is configured (even if availability check failed)
        has_api_key = (
            hasattr(self._macro_provider, "_api_key") and self._macro_provider._api_key is not None
        )

        if not fred_available:
            if not has_api_key:
                logger.info(
                    "FRED API key not configured; using yfinance proxies for rates",
                    provider=provider_name,
                    hint="Set COPINANCEOS_FRED_API_KEY in your .env file",
                )
            else:
                logger.warning(
                    "FRED availability check failed (API key configured but check failed); using yfinance proxies for rates",
                    provider=provider_name,
                    hint="Check your FRED API key and network connection",
                )
        else:
            logger.info("Using FRED for rates data", provider=provider_name)

        # Preferred FRED series
        fred_series = {
            "10y_nominal": ("DGS10", "percent"),
            "2y_nominal": ("DGS2", "percent"),
            "3m_nominal": ("DGS3MO", "percent"),
            "10y_real": ("DFII10", "percent"),
            "10y_breakeven": ("T10YIE", "percent"),
            "10y2y_curve": ("T10Y2Y", "percent"),
            "10y3m_curve": ("T10Y3M", "percent"),
        }

        # Try FRED if available
        if fred_available:
            out: dict[str, Any] = {"available": True, "source": "fred", "series": {}}
            try:
                for key, (series_id, unit) in fred_series.items():
                    points = await self._macro_provider.get_time_series(
                        series_id, start_date, end_date
                    )
                    metrics = _series_metrics(points)
                    metrics["unit"] = unit
                    out["series"][key] = metrics

                # Interpret 10Y "steady" using 20d change in bps (percent -> bps)
                teny = out["series"].get("10y_nominal", {})
                if teny.get("available") and "change_20d" in teny:
                    change_bps = float(teny["change_20d"]) * 100.0
                    out["interpretation"] = {
                        "10y_change_20d_bps": round(change_bps, 1),
                        "10y_trend": (
                            "steady"
                            if abs(change_bps) <= 15
                            else ("rising" if change_bps > 15 else "falling")
                        ),
                        "long_duration_pressure": "muted" if abs(change_bps) <= 15 else "elevated",
                    }
                logger.info("Successfully fetched rates from FRED", series_count=len(fred_series))
                return out
            except Exception as e:
                logger.warning("FRED rates block failed; falling back to proxies", error=str(e))

        # Fallback: yfinance proxies (limited)
        out = {"available": True, "source": "yfinance", "series": {}}
        try:
            # ^TNX is 10Y yield * 10. Convert to percent.
            prices = await self._market_provider.get_historical_data(
                "^TNX", start_date, end_date, interval="1d"
            )
            vals = [float(d.close_price) for d in prices if d.close_price is not None]
            if len(vals) < 2:
                return {"available": False, "source": "yfinance", "error": "No ^TNX data"}

            teny_pct = vals[-1] / 10.0
            out["series"]["10y_nominal_proxy"] = {
                "available": True,
                "latest": {
                    "timestamp": prices[-1].timestamp.isoformat(),
                    "value_percent": round(teny_pct, 3),
                },
                "data_points": len(vals),
            }
            return out
        except Exception as e:
            return {"available": False, "source": "yfinance", "error": str(e)}

    async def _get_credit_block(self, start_date: datetime, end_date: datetime) -> dict[str, Any]:
        # Check if FRED is available first
        fred_available = await self._macro_provider.is_available()
        provider_name = self._macro_provider.get_provider_name()

        # Check if API key is configured (even if availability check failed)
        has_api_key = (
            hasattr(self._macro_provider, "_api_key") and self._macro_provider._api_key is not None
        )

        if not fred_available:
            if not has_api_key:
                logger.info(
                    "FRED API key not configured; using yfinance proxies for credit",
                    provider=provider_name,
                    hint="Set COPINANCEOS_FRED_API_KEY in your .env file",
                )
            else:
                logger.warning(
                    "FRED availability check failed (API key configured but check failed); using yfinance proxies for credit",
                    provider=provider_name,
                    hint="Check your FRED API key and network connection",
                )
        else:
            logger.info("Using FRED for credit data", provider=provider_name)

        # Try FRED if available
        if fred_available:
            out: dict[str, Any] = {"available": True, "source": "fred", "series": {}}
            try:
                hy = await self._macro_provider.get_time_series(
                    "BAMLH0A0HYM2", start_date, end_date
                )
                ig = await self._macro_provider.get_time_series("BAMLC0A0CM", start_date, end_date)
                out["series"]["hy_oas_bps"] = _series_metrics(hy)
                out["series"]["ig_oas_bps"] = _series_metrics(ig)

                hy_metrics = out["series"]["hy_oas_bps"]
                if hy_metrics.get("available") and "change_20d" in hy_metrics:
                    tightening = float(hy_metrics["change_20d"]) < -10.0
                    out["interpretation"] = {
                        "hy_spreads": "tightening" if tightening else "widening_or_flat",
                        "risk_on_confirmation": tightening,
                    }
                logger.info("Successfully fetched credit spreads from FRED")
                return out
            except Exception as e:
                logger.warning("FRED credit block failed; falling back to proxies", error=str(e))

        # Fallback: HY vs IG ETF ratio (proxy for spread tightening)
        out = {"available": True, "source": "yfinance", "series": {}}
        try:
            hyg = await self._market_provider.get_historical_data(
                "HYG", start_date, end_date, interval="1d"
            )
            lqd = await self._market_provider.get_historical_data(
                "LQD", start_date, end_date, interval="1d"
            )
            hyg_prices = [float(d.close_price) for d in hyg if d.close_price is not None]
            lqd_prices = [float(d.close_price) for d in lqd if d.close_price is not None]
            if not hyg_prices or not lqd_prices:
                return {"available": False, "source": "yfinance", "error": "No HYG/LQD data"}
            ratio = hyg_prices[-1] / lqd_prices[-1] if lqd_prices[-1] else 0.0
            out["series"]["hyg_lqd_ratio"] = {
                "available": True,
                "latest_ratio": round(ratio, 4),
                "data_points": min(len(hyg_prices), len(lqd_prices)),
            }
            return out
        except Exception as e:
            return {"available": False, "source": "yfinance", "error": str(e)}

    async def _get_commodities_block(
        self, start_date: datetime, end_date: datetime
    ) -> dict[str, Any]:
        # Check if FRED is available first
        fred_available = await self._macro_provider.is_available()
        provider_name = self._macro_provider.get_provider_name()

        # Check if API key is configured (even if availability check failed)
        has_api_key = (
            hasattr(self._macro_provider, "_api_key") and self._macro_provider._api_key is not None
        )

        if not fred_available:
            if not has_api_key:
                logger.info(
                    "FRED API key not configured; using yfinance proxies for commodities",
                    provider=provider_name,
                    hint="Set COPINANCEOS_FRED_API_KEY in your .env file",
                )
            else:
                logger.warning(
                    "FRED availability check failed (API key configured but check failed); using yfinance proxies for commodities",
                    provider=provider_name,
                    hint="Check your FRED API key and network connection",
                )
        else:
            logger.info("Using FRED for commodities data", provider=provider_name)

        # Try FRED if available
        if fred_available:
            out: dict[str, Any] = {"available": True, "source": "fred", "series": {}}
            try:
                wti = await self._macro_provider.get_time_series("DCOILWTICO", start_date, end_date)
                metrics = _series_metrics(wti)
                metrics["unit"] = "usd_per_barrel"
                out["series"]["wti_spot"] = metrics

                if metrics.get("available") and "change_20d" in metrics:
                    # crude change in dollars is noisy; also compute approx % change using last 20 points
                    pts = _last_n(wti, 21)
                    if len(pts) >= 2 and pts[0].value:
                        pct = float(
                            (pts[-1].value - pts[0].value) / pts[0].value * _safe_decimal(100)
                        )
                        out["interpretation"] = {
                            "energy_impulse": (
                                "cooling" if pct < -5 else ("heating" if pct > 5 else "flat")
                            ),
                            "wti_change_20d_pct": round(pct, 2),
                        }
                logger.info("Successfully fetched commodities from FRED")
                return out
            except Exception as e:
                logger.warning(
                    "FRED commodities block failed; falling back to proxies", error=str(e)
                )

        out = {"available": True, "source": "yfinance", "series": {}}
        try:
            uso = await self._market_provider.get_historical_data(
                "USO", start_date, end_date, interval="1d"
            )
            vals = [float(d.close_price) for d in uso if d.close_price is not None]
            if len(vals) < 2:
                return {"available": False, "source": "yfinance", "error": "No USO data"}
            out["series"]["uso_proxy"] = {
                "available": True,
                "latest": {"timestamp": uso[-1].timestamp.isoformat(), "value": round(vals[-1], 4)},
                "data_points": len(vals),
            }
            return out
        except Exception as e:
            return {"available": False, "source": "yfinance", "error": str(e)}


def create_macro_regime_indicators_tool(
    macro_data_provider: MacroeconomicDataProvider,
    market_data_provider: MarketDataProvider,
) -> MacroRegimeIndicatorsTool:
    return MacroRegimeIndicatorsTool(macro_data_provider, market_data_provider)
