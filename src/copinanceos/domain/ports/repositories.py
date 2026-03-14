"""Repository interfaces (ports) for domain entities."""

from abc import ABC, abstractmethod
from uuid import UUID

from copinanceos.domain.models.market import MarketDataPoint
from copinanceos.domain.models.profile import AnalysisProfile
from copinanceos.domain.models.stock import Stock


class AnalysisProfileRepository(ABC):
    """Abstract repository for AnalysisProfile entities."""

    @abstractmethod
    async def get_by_id(self, profile_id: UUID) -> AnalysisProfile | None:
        """Get analysis profile by ID."""
        pass

    @abstractmethod
    async def save(self, profile: AnalysisProfile) -> AnalysisProfile:
        """Save or update analysis profile."""
        pass

    @abstractmethod
    async def delete(self, profile_id: UUID) -> bool:
        """Delete analysis profile by ID."""
        pass

    @abstractmethod
    async def list_all(self, limit: int = 100, offset: int = 0) -> list[AnalysisProfile]:
        """List all profiles with pagination."""
        pass


class StockRepository(ABC):
    """Abstract repository for Stock entities."""

    @abstractmethod
    async def get_by_symbol(self, symbol: str) -> Stock | None:
        """Get stock by symbol."""
        pass

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[Stock]:
        """Search stocks by query."""
        pass

    @abstractmethod
    async def save(self, stock: Stock) -> Stock:
        """Save or update stock."""
        pass

    @abstractmethod
    async def get_market_data(self, symbol: str, limit: int = 100) -> list[MarketDataPoint]:
        """Get historical market data."""
        pass
