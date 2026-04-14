"""Market domain models."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import Field

from copinance_os.domain.models.base import ValueObject
from copinance_os.domain.models.methodology import AnalysisMethodology


class MarketType(StrEnum):
    """Supported market segments for instrument-level analysis."""

    EQUITY = "equity"
    OPTIONS = "options"


class OptionSide(StrEnum):
    """Supported option contract sides."""

    CALL = "call"
    PUT = "put"
    ALL = "all"


class OptionGreeks(ValueObject):
    """Sensitivities for a European vanilla option under Black–Scholes–Merton.

    First-order Greeks come from QuantLib's ``AnalyticEuropeanEngine``. Higher-order
    analytics (vanna, charm, volga) use the same BSM inputs in closed form. Convention
    for ``theta``, ``vega``, and ``rho`` matches QuantLib's implementation (same units
    as ``EuropeanOption.theta()``, ``vega()``, and ``rho()``).
    """

    delta: Decimal = Field(..., description="Delta (∂V/∂S)")
    gamma: Decimal = Field(..., description="Gamma (∂²V/∂S²)")
    theta: Decimal = Field(..., description="Theta (time decay; QuantLib convention)")
    vega: Decimal = Field(..., description="Vega (∂V/∂σ; QuantLib convention)")
    rho: Decimal = Field(..., description="Rho (∂V/∂r; QuantLib convention)")
    vanna: Decimal | None = Field(default=None, description="Vanna (∂²V/∂S∂σ)")
    charm: Decimal | None = Field(default=None, description="Charm (∂Δ/∂T, calendar time)")
    volga: Decimal | None = Field(default=None, description="Volga (∂²V/∂σ²)")
    theoretical_price: Decimal | None = Field(
        default=None, description="BSM fair value (NPV) from the pricing engine"
    )
    itm_probability: Decimal | None = Field(
        default=None, description="Risk-neutral probability of expiring in the money"
    )


class MarketDataPoint(ValueObject):
    """Normalized market OHLCV data for a tradable instrument."""

    symbol: str = Field(..., description="Instrument symbol")
    timestamp: datetime = Field(..., description="Data timestamp")
    open_price: Decimal = Field(..., description="Opening price")
    close_price: Decimal = Field(..., description="Closing price")
    high_price: Decimal = Field(..., description="Highest price")
    low_price: Decimal = Field(..., description="Lowest price")
    volume: int = Field(..., description="Trading volume")
    metadata: dict[str, str] = Field(default_factory=dict, description="Additional metadata")


class OptionContract(ValueObject):
    """Normalized option contract snapshot."""

    underlying_symbol: str = Field(..., description="Underlying instrument symbol")
    contract_symbol: str = Field(..., description="Provider-specific option contract symbol")
    side: OptionSide = Field(..., description="Option side")
    strike: Decimal = Field(..., description="Strike price")
    expiration_date: date = Field(..., description="Expiration date")
    last_price: Decimal | None = Field(None, description="Last traded option price")
    bid: Decimal | None = Field(None, description="Best bid")
    ask: Decimal | None = Field(None, description="Best ask")
    volume: int | None = Field(None, description="Trading volume")
    open_interest: int | None = Field(None, description="Open interest")
    implied_volatility: Decimal | None = Field(None, description="Implied volatility")
    in_the_money: bool | None = Field(None, description="Whether the contract is in the money")
    currency: str | None = Field(None, description="Currency")
    greeks: OptionGreeks | None = Field(
        None,
        description="European BSM analytic Greeks when implied vol and spot are available",
    )
    metadata: dict[str, str] = Field(default_factory=dict, description="Additional metadata")


class OptionsChain(ValueObject):
    """Normalized options chain for an underlying instrument."""

    underlying_symbol: str = Field(..., description="Underlying instrument symbol")
    expiration_date: date = Field(..., description="Selected expiration date")
    available_expirations: list[date] = Field(
        default_factory=list,
        description="Available expirations exposed by the provider",
    )
    underlying_price: Decimal | None = Field(None, description="Underlying spot price")
    calls: list[OptionContract] = Field(default_factory=list, description="Call contracts")
    puts: list[OptionContract] = Field(default_factory=list, description="Put contracts")
    currency: str | None = Field(None, description="Currency")
    metadata: dict[str, str] = Field(default_factory=dict, description="Additional metadata")
    greeks_methodology: AnalysisMethodology | None = Field(
        default=None,
        description="Structured methodology for last BSM Greek enrichment pass, if any",
    )
