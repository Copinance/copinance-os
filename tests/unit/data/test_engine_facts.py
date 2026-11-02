"""Tests for copinance-os pure computational engine mode and fact injection."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from copinance_os import (
    FactBasedMarketProvider,
    FactNotFound,
    FactProviderNotConfigured,
    MarketFacts,
    NullFundamentalDataProvider,
    NullMacroDataProvider,
    NullMarketDataProvider,
)
from copinance_os.domain.models.market import MarketDataPoint
from copinance_os.infra.di import create_container, create_engine_container

pytestmark = pytest.mark.asyncio


async def test_default_container_is_engine_mode_fail_closed():
    """Default create_container() must not wire scraping vendor providers."""
    container = create_container(standalone=False)
    provider = container.market_data_provider()
    assert isinstance(provider, NullMarketDataProvider)
    assert not await provider.is_available()
    assert provider.get_provider_name() == "engine_null"

    with pytest.raises(FactProviderNotConfigured, match="get_quote"):
        await provider.get_quote("AAPL")


async def test_engine_container_with_injected_facts():
    """create_engine_container(facts) answers exclusively from in-memory facts."""
    now = datetime.now(UTC)
    facts = MarketFacts(
        symbol="AAPL",
        quote={"price": 240.50, "volume": 1000000},
        historical_data=[
            MarketDataPoint(
                symbol="AAPL",
                timestamp=now,
                open_price=Decimal("238.00"),
                high_price=Decimal("242.00"),
                low_price=Decimal("237.50"),
                close_price=Decimal("240.50"),
                volume=1000000,
            )
        ],
    )
    container = create_engine_container(facts=facts)
    provider = container.market_data_provider()
    assert isinstance(provider, FactBasedMarketProvider)
    assert await provider.is_available()
    assert provider.get_provider_name() == "fact_injection"

    # Known symbol returns injected fact
    quote = await provider.get_quote("AAPL")
    assert quote["price"] == 240.50

    # Case-insensitive
    quote_lower = await provider.get_quote("aapl")
    assert quote_lower["price"] == 240.50

    # Unknown symbol fails closed with FactNotFound
    with pytest.raises(FactNotFound, match="MSFT"):
        await provider.get_quote("MSFT")


async def test_standalone_flag_enables_vendor_providers():
    """Explicit standalone=True enables vendor adapters for standalone CLI."""
    container = create_container(standalone=True)
    provider = container.market_data_provider()
    assert not isinstance(provider, NullMarketDataProvider)
    assert provider.get_provider_name() != "engine_null"


async def test_fred_api_key_without_macro_wiring_fails_loud():
    """A bare fred_api_key with no standalone/macro override must raise, not degrade."""
    with pytest.raises(ValueError, match="macro_data_provider"):
        create_container(fred_api_key="demo-key")


async def test_fred_api_key_with_explicit_macro_provider_is_accepted():
    """An explicit macro_data_provider override satisfies the guard even in engine mode."""
    container = create_container(
        fred_api_key="demo-key",
        macro_data_provider=NullMacroDataProvider(),
    )
    assert isinstance(container.macro_data_provider(), NullMacroDataProvider)


async def test_fred_api_key_with_standalone_is_accepted():
    """standalone=True satisfies the guard and wires the real FRED provider."""
    container = create_container(fred_api_key="demo-key", standalone=True)
    provider = container.macro_data_provider()
    assert provider.get_provider_name() == "fred"


async def test_null_macro_and_fundamentals_fail_closed():
    """Null macro and fundamental providers reject queries in engine mode."""
    macro = NullMacroDataProvider()
    assert not await macro.is_available()
    with pytest.raises(FactProviderNotConfigured, match="get_time_series"):
        await macro.get_time_series("DGS10", None, None)

    funds = NullFundamentalDataProvider()
    assert not await funds.is_available()
    with pytest.raises(FactProviderNotConfigured, match="get_financial_statements"):
        await funds.get_financial_statements("AAPL", "income_statement")
