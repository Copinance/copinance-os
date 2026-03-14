"""Equity-specific domain models."""

from decimal import Decimal

from pydantic import Field

from copinanceos.domain.models.base import Entity


class Stock(Entity):
    """Stock entity representing a tradeable security."""

    symbol: str = Field(..., description="Stock ticker symbol")
    name: str = Field(..., description="Company name")
    exchange: str = Field(..., description="Stock exchange")
    sector: str | None = Field(None, description="Industry sector")
    industry: str | None = Field(None, description="Industry classification")
    market_cap: Decimal | None = Field(None, description="Market capitalization")
    # Company information
    website: str | None = Field(None, description="Company website")
    country: str | None = Field(None, description="Country")
    currency: str | None = Field(None, description="Currency")
    phone: str | None = Field(None, description="Phone number")
    city: str | None = Field(None, description="City")
    state: str | None = Field(None, description="State/Province")
    # Financial metrics
    enterprise_value: Decimal | None = Field(None, description="Enterprise value")
    shares_outstanding: int | None = Field(None, description="Shares outstanding")
    float_shares: int | None = Field(None, description="Float shares")
    beta: Decimal | None = Field(None, description="Beta")
    dividend_yield: Decimal | None = Field(None, description="Dividend yield")
    employees: int | None = Field(None, description="Number of employees")
    # Data source
    data_provider: str | None = Field(None, description="Data provider name")
