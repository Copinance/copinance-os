"""Stock fundamentals use cases."""

from copinance_os.domain.exceptions import InvalidStockSymbolError, ValidationError
from copinance_os.domain.models.fundamentals import (
    GetStockFundamentalsRequest,
    GetStockFundamentalsResponse,
)
from copinance_os.domain.ports.data_providers import FundamentalDataProvider
from copinance_os.research.workflows.base import UseCase

# Re-export for consumers that import from this module
__all__ = [
    "GetStockFundamentalsRequest",
    "GetStockFundamentalsResponse",
    "GetStockFundamentalsUseCase",
]


class GetStockFundamentalsUseCase(
    UseCase[GetStockFundamentalsRequest, GetStockFundamentalsResponse]
):
    """Use case for getting detailed stock fundamentals.

    This use case retrieves comprehensive fundamental data for a stock,
    including financial statements, ratios, and key metrics. It is provider-agnostic
    and works with any FundamentalDataProvider implementation.
    """

    def __init__(self, fundamental_data_provider: FundamentalDataProvider) -> None:
        self._fundamental_data_provider = fundamental_data_provider

    async def execute(self, request: GetStockFundamentalsRequest) -> GetStockFundamentalsResponse:
        if not request.symbol or not request.symbol.strip():
            raise InvalidStockSymbolError(request.symbol or "", reason="Symbol cannot be empty")

        if request.period_type not in ("annual", "quarterly"):
            raise ValidationError(
                "period_type",
                f"Invalid period_type: {request.period_type!r}. Must be 'annual' or 'quarterly'",
            )

        if request.periods < 1:
            raise ValidationError("periods", "periods must be at least 1")

        symbol = request.symbol.upper().strip()
        fundamentals = await self._fundamental_data_provider.get_detailed_fundamentals(
            symbol=symbol,
            periods=request.periods,
            period_type=request.period_type,
        )
        return GetStockFundamentalsResponse(fundamentals=fundamentals)
