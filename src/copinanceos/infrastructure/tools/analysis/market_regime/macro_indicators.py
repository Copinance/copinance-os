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
        return {
            "available": False,
            "error": "No data points",
            "data_points": 0,
            "latest": None,
            "change_20d": None,
            "unit": None,
        }

    pts = [p for p in points if p.value is not None]
    if not pts:
        return {
            "available": False,
            "error": "No valid values",
            "data_points": 0,
            "latest": None,
            "change_20d": None,
            "unit": None,
        }

    latest = pts[-1]
    # Ensure we have a valid numeric value
    try:
        latest_value = float(latest.value) if latest.value is not None else 0.0
    except (TypeError, ValueError) as e:
        logger.warning(f"Invalid latest value for series: {latest.value}, error: {e}")
        return {
            "available": False,
            "error": f"Invalid data type: {type(latest.value)}",
            "data_points": len(pts),
            "latest": None,
            "change_20d": None,
            "unit": None,
        }

    result: dict[str, Any] = {
        "available": True,
        "error": None,
        "latest": {"timestamp": latest.timestamp.isoformat(), "value": latest_value},
        "data_points": len(pts),
        "change_20d": None,
        "unit": None,
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
                    "include_labor": {
                        "type": "boolean",
                        "description": "Include labor market indicators (default: true)",
                        "default": True,
                    },
                    "include_housing": {
                        "type": "boolean",
                        "description": "Include housing market indicators (default: true)",
                        "default": True,
                    },
                    "include_manufacturing": {
                        "type": "boolean",
                        "description": "Include manufacturing indicators (default: true)",
                        "default": True,
                    },
                    "include_consumer": {
                        "type": "boolean",
                        "description": "Include consumer indicators (default: true)",
                        "default": True,
                    },
                    "include_global": {
                        "type": "boolean",
                        "description": "Include global market indicators (default: true)",
                        "default": True,
                    },
                    "include_advanced": {
                        "type": "boolean",
                        "description": "Include advanced economic indicators (default: true)",
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
            include_labor = bool(validated.get("include_labor", True))
            include_housing = bool(validated.get("include_housing", True))
            include_manufacturing = bool(validated.get("include_manufacturing", True))
            include_consumer = bool(validated.get("include_consumer", True))
            include_global = bool(validated.get("include_global", True))
            include_advanced = bool(validated.get("include_advanced", True))

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

            if include_labor:
                data["labor"] = await self._get_labor_block(start_date, end_date)

            if include_housing:
                data["housing"] = await self._get_housing_block(start_date, end_date)

            if include_manufacturing:
                data["manufacturing"] = await self._get_manufacturing_block(start_date, end_date)

            if include_consumer:
                data["consumer"] = await self._get_consumer_block(start_date, end_date)

            if include_global:
                data["global"] = await self._get_global_block(start_date, end_date)

            if include_advanced:
                data["advanced"] = await self._get_advanced_block(start_date, end_date)

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
            "10y2y_spread": (
                "T10Y2Y",
                "percent",
            ),  # Recession indicator - inverted = recession risk
            "10y3m_spread": ("T10Y3M", "percent"),
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

                # Interpret 10Y trend and yield curve inversion
                teny = out["series"].get("10y_nominal", {})
                teny2y_spread = out["series"].get("10y2y_spread", {})

                interpretation = {}

                if teny.get("available") and "change_20d" in teny:
                    change_bps = float(teny["change_20d"]) * 100.0
                    interpretation.update(
                        {
                            "10y_change_20d_bps": round(change_bps, 1),
                            "10y_trend": (
                                "steady"
                                if abs(change_bps) <= 15
                                else ("rising" if change_bps > 15 else "falling")
                            ),
                            "long_duration_pressure": (
                                "muted" if abs(change_bps) <= 15 else "elevated"
                            ),
                        }
                    )

                # Yield curve inversion analysis (10Y-2Y spread)
                if teny2y_spread.get("available") and "latest" in teny2y_spread:
                    spread_value = teny2y_spread["latest"]["value"]
                    interpretation.update(
                        {
                            "10y2y_spread_current": round(spread_value, 2),
                            "yield_curve_inverted": spread_value < 0,
                            "recession_risk": "elevated" if spread_value < 0 else "low",
                            "yield_curve_signal": (
                                "inverted_recession_warning"
                                if spread_value < -0.5
                                else (
                                    "inverted_mild_warning"
                                    if spread_value < 0
                                    else "normal" if spread_value > 1.0 else "flattening"
                                )
                            ),
                        }
                    )

                if interpretation:
                    out["interpretation"] = interpretation
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

                # Calculate HY-IG spread differential
                hy_metrics = out["series"]["hy_oas_bps"]
                ig_metrics = out["series"]["ig_oas_bps"]
                if (
                    hy_metrics.get("available")
                    and ig_metrics.get("available")
                    and "latest" in hy_metrics
                    and "latest" in ig_metrics
                ):
                    hy_latest = hy_metrics["latest"]["value"]
                    ig_latest = ig_metrics["latest"]["value"]
                    differential = hy_latest - ig_latest
                    out["series"]["hy_ig_differential_bps"] = {
                        "available": True,
                        "latest": {
                            "timestamp": hy_metrics["latest"]["timestamp"],  # Use HY timestamp
                            "value": round(differential, 1),
                        },
                        "data_points": min(hy_metrics["data_points"], ig_metrics["data_points"]),
                        "unit": "bps",
                    }

                hy_metrics = out["series"]["hy_oas_bps"]
                ig_metrics = out["series"]["ig_oas_bps"]
                differential_metrics = out["series"].get("hy_ig_differential_bps", {})

                interpretation = {}

                # HY spread analysis
                if hy_metrics.get("available") and hy_metrics.get("change_20d") is not None:
                    hy_change = float(hy_metrics["change_20d"])
                    hy_tightening = hy_change < -10.0
                    interpretation.update(
                        {
                            "hy_spreads": "tightening" if hy_tightening else "widening_or_flat",
                            "hy_change_20d_bps": round(hy_change, 1),
                            "risk_on_confirmation": hy_tightening,
                        }
                    )

                # IG spread analysis
                if ig_metrics.get("available") and ig_metrics.get("change_20d") is not None:
                    ig_change = float(ig_metrics["change_20d"])
                    ig_tightening = ig_change < -5.0  # IG spreads are typically tighter
                    interpretation.update(
                        {
                            "ig_spreads": "tightening" if ig_tightening else "widening_or_flat",
                            "ig_change_20d_bps": round(ig_change, 1),
                        }
                    )

                # HY-IG differential analysis (credit quality relative valuation)
                if differential_metrics.get("available") and "latest" in differential_metrics:
                    diff_value = differential_metrics["latest"]["value"]
                    interpretation.update(
                        {
                            "hy_ig_differential_current_bps": round(diff_value, 1),
                            "credit_quality_valuation": (
                                "hy_cheap_vs_ig"
                                if diff_value > 400  # Typical range 200-600bps
                                else (
                                    "hy_expensive_vs_ig" if diff_value < 200 else "normal_valuation"
                                )
                            ),
                            "credit_market_stress": "elevated" if diff_value > 500 else "normal",
                        }
                    )

                if interpretation:
                    out["interpretation"] = interpretation
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

    async def _get_labor_block(self, start_date: datetime, end_date: datetime) -> dict[str, Any]:
        """Labor market indicators: unemployment, payrolls, JOLTS."""
        fred_available = await self._macro_provider.is_available()

        has_api_key = (
            hasattr(self._macro_provider, "_api_key") and self._macro_provider._api_key is not None
        )

        if not fred_available:
            if not has_api_key:
                logger.info("FRED API key not configured; skipping labor market indicators")
            else:
                logger.warning("FRED availability check failed; skipping labor market indicators")
            return {"available": False, "source": "fred", "error": "FRED not available"}

        out: dict[str, Any] = {"available": True, "source": "fred", "series": {}}
        try:
            # Labor market indicators
            fred_series = {
                "unemployment_rate": ("UNRATE", "percent"),
                "nonfarm_payrolls": ("PAYEMS", "thousands"),  # Monthly change
                "jolts_openings": ("JTSJOL", "thousands"),  # Job openings
                "jolts_hires": ("JTSHIR", "thousands"),
                "jolts_separations": ("JTSTSR", "rate"),  # Total separations rate
                "jolts_quits": ("JTSQUR", "thousands"),
            }

            for key, (series_id, unit) in fred_series.items():
                points = await self._macro_provider.get_time_series(series_id, start_date, end_date)
                metrics = _series_metrics(points)
                metrics["unit"] = unit
                out["series"][key] = metrics

            # Interpret labor market conditions
            unemployment = out["series"].get("unemployment_rate", {})
            payrolls = out["series"].get("nonfarm_payrolls", {})

            interpretation = {}
            if unemployment.get("available") and "latest" in unemployment:
                urate = unemployment["latest"]["value"]
                interpretation["unemployment_current"] = round(urate, 1)
                interpretation["labor_market_tightness"] = (
                    "very_tight"
                    if urate < 3.5
                    else "tight" if urate < 4.5 else "normal" if urate < 6.0 else "loose"
                )

            if payrolls.get("available") and payrolls.get("change_20d") is not None:
                payroll_change = float(payrolls["change_20d"])
                interpretation["payroll_trend"] = (
                    "strong_growth"
                    if payroll_change > 200
                    else (
                        "moderate_growth"
                        if payroll_change > 100
                        else "weak_growth" if payroll_change > 0 else "declining"
                    )
                )

            if interpretation:
                out["interpretation"] = interpretation

            logger.info("Successfully fetched labor market indicators from FRED")
            return out
        except Exception as e:
            logger.warning("FRED labor block failed", error=str(e))
            return {"available": False, "source": "fred", "error": str(e)}

    async def _get_housing_block(self, start_date: datetime, end_date: datetime) -> dict[str, Any]:
        """Housing market indicators: new/existing sales, Case-Shiller."""
        fred_available = await self._macro_provider.is_available()

        has_api_key = (
            hasattr(self._macro_provider, "_api_key") and self._macro_provider._api_key is not None
        )

        if not fred_available:
            if not has_api_key:
                logger.info("FRED API key not configured; skipping housing indicators")
            else:
                logger.warning("FRED availability check failed; skipping housing indicators")
            return {"available": False, "source": "fred", "error": "FRED not available"}

        out: dict[str, Any] = {"available": True, "source": "fred", "series": {}}
        try:
            # Housing market indicators
            fred_series = {
                "new_home_sales": ("HSN1F", "thousands"),  # Monthly
                "existing_home_sales": ("EXHOSLUSM495S", "thousands"),  # Monthly
                "case_shiller_20_city": ("CSUSHPISA", "index_2000_100"),  # Monthly index
                "case_shiller_10_city": ("SPCS10RSA", "index_2000_100"),
                "fhfa_house_price_index": ("USSTHPI", "index_1991_100"),
                "housing_starts": ("HOUST", "thousands"),
                "building_permits": ("PERMIT", "thousands"),
            }

            for key, (series_id, unit) in fred_series.items():
                points = await self._macro_provider.get_time_series(series_id, start_date, end_date)
                metrics = _series_metrics(points)
                metrics["unit"] = unit
                out["series"][key] = metrics

            # Interpret housing market conditions
            cs_index = out["series"].get("case_shiller_20_city", {})
            new_sales = out["series"].get("new_home_sales", {})

            interpretation = {}
            if cs_index.get("available") and cs_index.get("change_20d") is not None:
                price_change_pct = float(cs_index["change_20d"]) / cs_index["latest"]["value"] * 100
                interpretation["home_price_trend_3m_pct"] = round(price_change_pct, 2)
                interpretation["housing_market_momentum"] = (
                    "strong_appreciation"
                    if price_change_pct > 2.0
                    else (
                        "moderate_appreciation"
                        if price_change_pct > 0.5
                        else "flat" if price_change_pct > -0.5 else "declining"
                    )
                )

            if new_sales.get("available") and "latest" in new_sales:
                sales_level = new_sales["latest"]["value"]
                interpretation["new_home_sales_level"] = round(sales_level, 0)
                interpretation["housing_demand"] = (
                    "strong" if sales_level > 700 else "moderate" if sales_level > 500 else "weak"
                )

            if interpretation:
                out["interpretation"] = interpretation

            logger.info("Successfully fetched housing indicators from FRED")
            return out
        except Exception as e:
            logger.warning("FRED housing block failed", error=str(e))
            return {"available": False, "source": "fred", "error": str(e)}

    async def _get_manufacturing_block(
        self, start_date: datetime, end_date: datetime
    ) -> dict[str, Any]:
        """Manufacturing indicators: ISM, industrial production, capacity utilization."""
        fred_available = await self._macro_provider.is_available()

        has_api_key = (
            hasattr(self._macro_provider, "_api_key") and self._macro_provider._api_key is not None
        )

        if not fred_available:
            if not has_api_key:
                logger.info("FRED API key not configured; skipping manufacturing indicators")
            else:
                logger.warning("FRED availability check failed; skipping manufacturing indicators")
            return {"available": False, "source": "fred", "error": "FRED not available"}

        out: dict[str, Any] = {"available": True, "source": "fred", "series": {}}
        try:
            # Manufacturing indicators
            fred_series = {
                "industrial_production": ("INDPRO", "index_2017_100"),
                "capacity_utilization": ("TCU", "percent"),
                "manufacturing_ip": ("IPMAN", "index_2017_100"),  # Manufacturing IP specifically
                "durable_goods_orders": (
                    "NEWORDER",
                    "millions_dollars",
                ),  # New Orders for Durable Goods
                "factory_orders": (
                    "AMTMTI",
                    "millions_dollars",
                ),  # Manufacturers' Total Inventories
                "durable_goods_ex_transport": (
                    "DMANEMP",
                    "millions_dollars",
                ),  # Durable manufacturing
            }

            for key, (series_id, unit) in fred_series.items():
                points = await self._macro_provider.get_time_series(series_id, start_date, end_date)
                metrics = _series_metrics(points)
                metrics["unit"] = unit
                out["series"][key] = metrics

            # Interpret manufacturing conditions
            ip = out["series"].get("industrial_production", {})
            capacity = out["series"].get("capacity_utilization", {})
            durable_orders = out["series"].get("durable_goods_orders", {})

            interpretation = {}
            if capacity.get("available") and "latest" in capacity:
                cap_rate = capacity["latest"]["value"]
                interpretation["capacity_utilization"] = round(cap_rate, 1)
                interpretation["manufacturing_capacity"] = (
                    "near_full" if cap_rate > 80 else "normal" if cap_rate > 75 else "underutilized"
                )

            if ip.get("available") and ip.get("change_20d") is not None:
                ip_change_pct = float(ip["change_20d"]) / ip["latest"]["value"] * 100
                interpretation["industrial_production_trend_3m_pct"] = round(ip_change_pct, 2)

            if durable_orders.get("available") and durable_orders.get("change_20d") is not None:
                orders_change = float(durable_orders["change_20d"])
                interpretation["durable_orders_trend"] = (
                    "strong" if orders_change > 5 else "moderate" if orders_change > 0 else "weak"
                )

            if interpretation:
                out["interpretation"] = interpretation

            logger.info("Successfully fetched manufacturing indicators from FRED")
            return out
        except Exception as e:
            logger.warning("FRED manufacturing block failed", error=str(e))
            return {"available": False, "source": "fred", "error": str(e)}

    async def _get_consumer_block(self, start_date: datetime, end_date: datetime) -> dict[str, Any]:
        """Consumer indicators: retail sales, confidence, spending."""
        fred_available = await self._macro_provider.is_available()

        has_api_key = (
            hasattr(self._macro_provider, "_api_key") and self._macro_provider._api_key is not None
        )

        if not fred_available:
            if not has_api_key:
                logger.info("FRED API key not configured; skipping consumer indicators")
            else:
                logger.warning("FRED availability check failed; skipping consumer indicators")
            return {"available": False, "source": "fred", "error": "FRED not available"}

        out: dict[str, Any] = {"available": True, "source": "fred", "series": {}}
        try:
            # Consumer indicators
            fred_series = {
                "retail_sales": ("RRSFS", "millions_dollars"),  # Retail and Food Services Sales
                "retail_sales_mom": ("RRSFS", "percent_change"),  # Will calculate change
                "consumer_confidence": ("UMCSENT", "index_1966_100"),  # University of Michigan
                "personal_consumption": (
                    "PCEC",
                    "billions_dollars",
                ),  # Personal Consumption Expenditures
                "personal_income": ("PI", "billions_dollars"),  # Personal Income
                "personal_saving_rate": ("PSAVERT", "percent"),
                "real_pce": ("PCEC96", "billions_chained_2012_dollars"),  # Real PCE
            }

            for key, (series_id, unit) in fred_series.items():
                points = await self._macro_provider.get_time_series(series_id, start_date, end_date)
                metrics = _series_metrics(points)
                metrics["unit"] = unit
                out["series"][key] = metrics

            # Calculate retail sales month-over-month change
            if out["series"]["retail_sales"].get("available"):
                sales_points = await self._macro_provider.get_time_series(
                    "RSXFS", start_date, end_date
                )
                if len(sales_points) >= 2:
                    latest_sales = sales_points[-1].value
                    prev_sales = sales_points[-2].value
                    if prev_sales and latest_sales:
                        mom_change = (latest_sales - prev_sales) / prev_sales * 100
                        out["series"]["retail_sales_mom"] = {
                            "available": True,
                            "latest": {
                                "timestamp": sales_points[-1].timestamp.isoformat(),
                                "value": round(mom_change, 2),
                            },
                            "data_points": len(sales_points),
                            "unit": "percent_change",
                        }

            # Interpret consumer conditions
            confidence = out["series"].get("consumer_confidence", {})
            retail_mom = out["series"].get("retail_sales_mom", {})
            saving_rate = out["series"].get("personal_saving_rate", {})
            pce = out["series"].get("personal_consumption", {})

            interpretation = {}
            if confidence.get("available") and "latest" in confidence:
                conf_level = confidence["latest"]["value"]
                interpretation["consumer_confidence_current"] = round(conf_level, 1)
                interpretation["consumer_sentiment"] = (
                    "optimistic"
                    if conf_level > 80
                    else "neutral" if conf_level > 60 else "pessimistic"
                )

            if pce.get("available") and pce.get("change_20d") is not None:
                pce_change = float(pce["change_20d"])
                interpretation["pce_trend"] = (
                    "strong_growth"
                    if pce_change > 50
                    else (
                        "moderate_growth"
                        if pce_change > 20
                        else "weak_growth" if pce_change > 0 else "declining"
                    )
                )

            if retail_mom.get("available") and "latest" in retail_mom:
                mom_pct = retail_mom["latest"]["value"]
                interpretation["retail_sales_mom_pct"] = round(mom_pct, 2)
                interpretation["retail_trend"] = (
                    "strong" if mom_pct > 1.0 else "moderate" if mom_pct > 0.0 else "weak"
                )

            if saving_rate.get("available") and "latest" in saving_rate:
                save_rate = saving_rate["latest"]["value"]
                interpretation["saving_rate_current"] = round(save_rate, 1)

            if interpretation:
                out["interpretation"] = interpretation

            logger.info("Successfully fetched consumer indicators from FRED")
            return out
        except Exception as e:
            logger.warning("FRED consumer block failed", error=str(e))
            return {"available": False, "source": "fred", "error": str(e)}

    async def _get_global_block(self, start_date: datetime, end_date: datetime) -> dict[str, Any]:
        """Global indicators: FX rates, emerging market flows."""
        # Use market data provider for FX rates
        out: dict[str, Any] = {"available": True, "source": "yfinance", "series": {}}
        try:
            # FX rates
            fx_pairs = {
                "eur_usd": "EURUSD=X",
                "usd_jpy": "JPY=X",
                "gbp_usd": "GBPUSD=X",
                "usd_chf": "CHF=X",
                "aud_usd": "AUDUSD=X",
                "usd_cad": "CAD=X",
            }

            for key, ticker in fx_pairs.items():
                prices = await self._market_provider.get_historical_data(
                    ticker, start_date, end_date, interval="1d"
                )
                if prices:
                    vals = [float(d.close_price) for d in prices if d.close_price is not None]
                    if vals:
                        latest_val = vals[-1]
                        prev_val = vals[0] if len(vals) > 1 else latest_val
                        change_pct = (
                            (latest_val - prev_val) / prev_val * 100 if prev_val != 0 else 0
                        )

                        out["series"][key] = {
                            "available": True,
                            "latest": {
                                "timestamp": prices[-1].timestamp.isoformat(),
                                "value": round(latest_val, 4),
                            },
                            "change_20d_pct": round(change_pct, 2),
                            "data_points": len(vals),
                            "unit": "currency",
                        }

            # Emerging market ETF proxies (if available through yfinance)
            em_tickers = [
                "VWO",
                "EEM",
            ]  # Vanguard FTSE Emerging Markets, iShares MSCI Emerging Markets
            for ticker in em_tickers:
                try:
                    prices = await self._market_provider.get_historical_data(
                        ticker, start_date, end_date, interval="1d"
                    )
                    if prices:
                        vals = [float(d.close_price) for d in prices if d.close_price is not None]
                        if vals:
                            out["series"][f"em_{ticker.lower()}_proxy"] = {
                                "available": True,
                                "latest": {
                                    "timestamp": prices[-1].timestamp.isoformat(),
                                    "value": round(vals[-1], 2),
                                },
                                "data_points": len(vals),
                                "unit": "usd",
                            }
                except Exception:
                    continue  # Skip if ticker not available

            # Interpret FX and EM trends
            eur_usd = out["series"].get("eur_usd", {})
            usd_jpy = out["series"].get("usd_jpy", {})

            interpretation = {}
            if eur_usd.get("available") and "change_20d_pct" in eur_usd:
                eur_change = eur_usd["change_20d_pct"]
                interpretation["usd_strength_vs_eur"] = (
                    "usd_weakening"
                    if eur_change > 2.0
                    else "usd_steady" if abs(eur_change) < 2.0 else "usd_strengthening"
                )

            if usd_jpy.get("available") and "change_20d_pct" in usd_jpy:
                jpy_change = usd_jpy["change_20d_pct"]
                interpretation["usd_strength_vs_jpy"] = (
                    "usd_weakening"
                    if jpy_change > 2.0
                    else "usd_steady" if abs(jpy_change) < 2.0 else "usd_strengthening"
                )

            if interpretation:
                out["interpretation"] = interpretation

            logger.info("Successfully fetched global indicators")
            return out
        except Exception as e:
            logger.warning("Global indicators block failed", error=str(e))
            return {"available": False, "source": "yfinance", "error": str(e)}

    async def _get_advanced_block(self, start_date: datetime, end_date: datetime) -> dict[str, Any]:
        """Advanced indicators: LEI, CDS spreads, Fed balance sheet."""
        fred_available = await self._macro_provider.is_available()

        out: dict[str, Any] = {"available": True, "source": "mixed", "series": {}}

        # Try FRED first for LEI and other advanced indicators
        if fred_available:
            try:
                # Leading Economic Index
                lei_points = await self._macro_provider.get_time_series(
                    "USSLIND", start_date, end_date
                )
                lei_metrics = _series_metrics(lei_points)
                lei_metrics["unit"] = "index_2010_100"
                out["series"]["leading_economic_index"] = lei_metrics

                # Federal Reserve Balance Sheet (weekly)
                fed_bs_points = await self._macro_provider.get_time_series(
                    "WALCL", start_date, end_date
                )
                fed_bs_metrics = _series_metrics(fed_bs_points)
                fed_bs_metrics["unit"] = "billions_dollars"
                out["series"]["fed_balance_sheet"] = fed_bs_metrics

                # Interpret advanced indicators
                lei = out["series"].get("leading_economic_index", {})
                fed_bs = out["series"].get("fed_balance_sheet", {})

                interpretation = {}
                if lei.get("available") and "change_20d" in lei:
                    lei_change = float(lei["change_20d"])
                    interpretation["lei_trend"] = (
                        "improving"
                        if lei_change > 0.5
                        else "stable" if abs(lei_change) < 0.5 else "deteriorating"
                    )

                if fed_bs.get("available") and "latest" in fed_bs:
                    bs_size = fed_bs["latest"]["value"]
                    interpretation["fed_balance_sheet_trillions"] = round(bs_size / 1000, 2)

                if interpretation:
                    out["interpretation"] = interpretation

                logger.info("Successfully fetched advanced FRED indicators")
            except Exception as e:
                logger.warning("FRED advanced indicators failed", error=str(e))

        # Try yfinance for CDS proxies (limited availability)
        try:
            # CDS index proxies - these may not be available in yfinance
            cds_proxies = ["HYG", "LQD"]  # Could use spreads between these as rough proxy
            for ticker in cds_proxies:
                try:
                    prices = await self._market_provider.get_historical_data(
                        ticker, start_date, end_date, interval="1d"
                    )
                    if prices:
                        vals = [float(d.close_price) for d in prices if d.close_price is not None]
                        if vals:
                            out["series"][f"cds_proxy_{ticker.lower()}"] = {
                                "available": True,
                                "latest": {
                                    "timestamp": prices[-1].timestamp.isoformat(),
                                    "value": round(vals[-1], 2),
                                },
                                "data_points": len(vals),
                                "unit": "usd",
                            }
                except Exception:
                    continue

            logger.info("Successfully fetched advanced market indicators")
        except Exception as e:
            logger.warning("Advanced market indicators failed", error=str(e))

        if not out["series"]:
            return {
                "available": False,
                "source": "mixed",
                "error": "No advanced indicators available",
            }

        return out


def create_macro_regime_indicators_tool(
    macro_data_provider: MacroeconomicDataProvider,
    market_data_provider: MarketDataProvider,
) -> MacroRegimeIndicatorsTool:
    return MacroRegimeIndicatorsTool(macro_data_provider, market_data_provider)
