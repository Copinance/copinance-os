"""Unit tests for fundamentals use cases."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from copinanceos.application.use_cases.fundamentals import (
    GetStockFundamentalsRequest,
    GetStockFundamentalsUseCase,
)
from copinanceos.domain.exceptions import InvalidStockSymbolError, ValidationError
from copinanceos.domain.models.fundamentals import StockFundamentals
from copinanceos.domain.ports.data_providers import FundamentalDataProvider


@pytest.mark.unit
class TestFundamentalsUseCases:
    """Test fundamentals-related use cases."""

    @pytest.mark.asyncio
    async def test_research_fundamentals_validation_empty_symbol(
        self,
        fundamental_data_provider: FundamentalDataProvider,
    ) -> None:
        """Test that empty symbol is rejected."""
        use_case = GetStockFundamentalsUseCase(fundamental_data_provider)
        request = GetStockFundamentalsRequest(
            symbol="",
            periods=1,
            period_type="annual",
        )

        with pytest.raises(InvalidStockSymbolError, match="Symbol cannot be empty"):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_research_fundamentals_validation_invalid_period_type(
        self,
        fundamental_data_provider: FundamentalDataProvider,
    ) -> None:
        """Test that invalid period type is rejected."""
        use_case = GetStockFundamentalsUseCase(fundamental_data_provider)
        request = GetStockFundamentalsRequest(
            symbol="AAPL",
            periods=1,
            period_type="invalid",
        )

        with pytest.raises(ValidationError, match="Invalid period_type"):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_research_fundamentals_validation_invalid_periods(
        self,
        fundamental_data_provider: FundamentalDataProvider,
    ) -> None:
        """Test that invalid periods count is rejected."""
        use_case = GetStockFundamentalsUseCase(fundamental_data_provider)
        request = GetStockFundamentalsRequest(
            symbol="AAPL",
            periods=0,
            period_type="annual",
        )

        with pytest.raises(ValidationError, match="periods must be at least 1"):
            await use_case.execute(request)

    @pytest.mark.asyncio
    async def test_research_fundamentals_symbol_normalization(
        self,
        fundamental_data_provider: FundamentalDataProvider,
    ) -> None:
        """Test that symbol is normalized to uppercase."""
        # Mock the provider to return a fundamentals object
        mock_fundamentals = StockFundamentals(
            symbol="AAPL",
            provider="test",
            data_as_of=datetime.now(UTC),
        )

        fundamental_data_provider.get_detailed_fundamentals = AsyncMock(
            return_value=mock_fundamentals
        )

        use_case = GetStockFundamentalsUseCase(fundamental_data_provider)
        request = GetStockFundamentalsRequest(
            symbol="aapl",
            periods=1,
            period_type="annual",
        )

        response = await use_case.execute(request)
        assert response.fundamentals.symbol == "AAPL"
