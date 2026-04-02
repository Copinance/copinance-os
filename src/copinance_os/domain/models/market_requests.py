"""Market data request/response models (provider-agnostic DTOs)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from copinance_os.domain.models.market import MarketDataPoint, OptionsChain
from copinance_os.domain.models.stock import Stock


class GetInstrumentRequest(BaseModel):
    """Request to get equity instrument information by symbol."""

    symbol: str = Field(..., description="Instrument symbol")


class GetInstrumentResponse(BaseModel):
    """Response from getting instrument information."""

    instrument: Stock | None = Field(..., description="Instrument if found")


class GetQuoteRequest(BaseModel):
    """Request to get current market quote for a symbol."""

    symbol: str = Field(..., description="Instrument symbol")


class GetQuoteResponse(BaseModel):
    """Response with current quote data."""

    quote: dict[str, Any] = Field(default_factory=dict, description="Quote payload from provider")
    symbol: str = Field(..., description="Instrument symbol")


class GetHistoricalDataRequest(BaseModel):
    """Request to get historical OHLCV data for a symbol."""

    symbol: str = Field(..., description="Instrument symbol")
    start_date: datetime = Field(..., description="Start date (inclusive)")
    end_date: datetime = Field(..., description="End date (inclusive)")
    interval: str = Field(default="1d", description="Bar interval (e.g. 1d, 1h, 5m)")


class GetHistoricalDataResponse(BaseModel):
    """Response with historical market data points."""

    data: list[MarketDataPoint] = Field(
        default_factory=list,
        description="Historical OHLCV data points",
    )
    symbol: str = Field(..., description="Instrument symbol")


class GetOptionsChainRequest(BaseModel):
    """Request to get options chain for an underlying symbol."""

    underlying_symbol: str = Field(..., description="Underlying instrument symbol")
    expiration_date: str | None = Field(
        None,
        description="Optional expiration date (YYYY-MM-DD); provider default if omitted",
    )


class GetOptionsChainResponse(BaseModel):
    """Response with options chain."""

    chain: OptionsChain = Field(..., description="Options chain for the underlying")
    underlying_symbol: str = Field(..., description="Underlying instrument symbol")
