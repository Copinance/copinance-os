"""Normalize provider outputs to ``PriceSeries`` and sorted point lists."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import structlog
from pydantic import BaseModel, Field

from copinance_os.data.schemas.price_series import PriceSeries
from copinance_os.domain.models.market import MarketDataPoint

logger = structlog.get_logger(__name__)


class CoerceMarketDataPointsResult(BaseModel):
    """Outcome of coercing a mixed sequence to ``MarketDataPoint`` (sorted oldest first)."""

    model_config = {"frozen": True}

    points: list[MarketDataPoint] = Field(description="Valid points, sorted by timestamp")
    accepted_as_model: int = Field(ge=0, description="Items already ``MarketDataPoint``")
    accepted_from_dict: int = Field(ge=0, description="Dicts validated successfully")
    skipped_invalid_dict: int = Field(ge=0, description="Dicts that failed validation")
    skipped_unsupported_type: int = Field(
        ge=0, description="Non-dict, non-``MarketDataPoint`` items"
    )


def coerce_sorted_market_data_points_detailed(
    data_points: Sequence[Any],
    *,
    strict: bool = False,
) -> CoerceMarketDataPointsResult:
    """Coerce mixed points to ``MarketDataPoint``, sort by timestamp, track skips.

    In non-strict mode, invalid or unsupported entries are omitted and counted; a warning
    is logged when any skip occurred. In strict mode, the first invalid dict or
    unsupported type raises ``ValueError`` or ``TypeError``.
    """
    out: list[MarketDataPoint] = []
    accepted_as_model = 0
    accepted_from_dict = 0
    skipped_invalid_dict = 0
    skipped_unsupported_type = 0

    for p in data_points:
        if isinstance(p, MarketDataPoint):
            out.append(p)
            accepted_as_model += 1
        elif isinstance(p, dict):
            try:
                out.append(MarketDataPoint.model_validate(p))
                accepted_from_dict += 1
            except Exception as e:
                if strict:
                    raise ValueError(f"Invalid market data point dict: {e}") from e
                skipped_invalid_dict += 1
                logger.debug("skip_invalid_market_point", error=str(e))
        else:
            if strict:
                raise TypeError(
                    f"Unsupported market data point type {type(p).__name__!r}; "
                    "expected MarketDataPoint or dict"
                )
            skipped_unsupported_type += 1
            logger.debug("skip_unsupported_market_point_type", type=type(p).__name__)

    sorted_pts = sorted(out, key=lambda x: x.timestamp)
    result = CoerceMarketDataPointsResult(
        points=sorted_pts,
        accepted_as_model=accepted_as_model,
        accepted_from_dict=accepted_from_dict,
        skipped_invalid_dict=skipped_invalid_dict,
        skipped_unsupported_type=skipped_unsupported_type,
    )

    total_skips = skipped_invalid_dict + skipped_unsupported_type
    if total_skips > 0:
        logger.warning(
            "market_data_points_coercion_skipped",
            accepted_models=accepted_as_model,
            accepted_from_dicts=accepted_from_dict,
            skipped_invalid_dict=skipped_invalid_dict,
            skipped_unsupported_type=skipped_unsupported_type,
            total_input=len(data_points),
            output_points=len(sorted_pts),
        )

    return result


def coerce_sorted_market_data_points(
    data_points: Sequence[Any],
    *,
    strict: bool = False,
) -> list[MarketDataPoint]:
    """Coerce mixed points to ``MarketDataPoint`` and sort by timestamp (oldest first).

    See ``coerce_sorted_market_data_points_detailed`` for skip statistics and ``strict``.
    """
    return coerce_sorted_market_data_points_detailed(data_points, strict=strict).points


def price_series_from_market_data_points(points: Sequence[MarketDataPoint]) -> PriceSeries:
    """Build a chronologically ordered close series from OHLCV points."""
    if not points:
        raise ValueError("Cannot build PriceSeries from empty market data")
    ordered = sorted(points, key=lambda p: p.timestamp)
    closes = [float(p.close_price) for p in ordered]
    timestamps = [p.timestamp for p in ordered]
    return PriceSeries(closes=closes, timestamps=timestamps)
