"""Stock fundamentals use cases."""

from pydantic import BaseModel, Field

from copinance_os.domain.exceptions import InvalidStockSymbolError, ValidationError
from copinance_os.domain.models.fundamentals import StockFundamentals
from copinance_os.domain.ports.data_providers import FundamentalDataProvider
from copinance_os.research.workflows.base import UseCase


class GetStockFundamentalsRequest(BaseModel):
    """Request for stock fundamentals."""

    symbol: str = Field(..., description="Stock symbol to analyze")
    periods: int = Field(default=5, description="Number of periods to retrieve (e.g., 5 years)")
    period_type: str = Field(default="annual", description="Period type: 'annual' or 'quarterly'")


class GetStockFundamentalsResponse(BaseModel):
    """Response from getting stock fundamentals."""

    fundamentals: StockFundamentals = Field(..., description="Comprehensive stock fundamentals")


class GetStockFundamentalsUseCase(
    UseCase[GetStockFundamentalsRequest, GetStockFundamentalsResponse]
):
    """Use case for getting detailed stock fundamentals.

    This use case retrieves comprehensive fundamental data for a stock,
    including financial statements, ratios, and key metrics. It is provider-agnostic
    and works with any FundamentalDataProvider implementation.
    """

    def __init__(self, fundamental_data_provider: FundamentalDataProvider) -> None:
        """Initialize use case.

        Args:
            fundamental_data_provider: Provider for fundamental data
        """
        self._fundamental_data_provider = fundamental_data_provider

    async def execute(self, request: GetStockFundamentalsRequest) -> GetStockFundamentalsResponse:
        """Execute the stock fundamentals use case.

        Args:
            request: Request containing symbol and parameters

        Returns:
            Response with comprehensive fundamentals data

        Raises:
            InvalidStockSymbolError: If symbol is invalid
            ValidationError: If request parameters are invalid
        """
        if not request.symbol or not request.symbol.strip():
            raise InvalidStockSymbolError(request.symbol or "", reason="Symbol cannot be empty")

        if request.period_type not in ("annual", "quarterly"):
            raise ValidationError(
                "period_type",
                f"Invalid period_type: {request.period_type}. Must be 'annual' or 'quarterly'",
            )

        if request.periods < 1:
            raise ValidationError("periods", "periods must be at least 1")

        # Retrieve detailed fundamentals from provider
        fundamentals = await self._fundamental_data_provider.get_detailed_fundamentals(
            symbol=request.symbol.strip().upper(),
            periods=request.periods,
            period_type=request.period_type,
        )

        return GetStockFundamentalsResponse(fundamentals=fundamentals)
