"""Repository interfaces (ports) for domain entities."""

from abc import ABC, abstractmethod
from uuid import UUID

from copinanceos.domain.models.research_profile import ResearchProfile
from copinanceos.domain.models.stock import Stock, StockData


class ResearchProfileRepository(ABC):
    """Abstract repository for ResearchProfile entities."""

    @abstractmethod
    async def get_by_id(self, profile_id: UUID) -> ResearchProfile | None:
        """Get research profile by ID."""
        pass

    @abstractmethod
    async def save(self, profile: ResearchProfile) -> ResearchProfile:
        """Save or update research profile."""
        pass

    @abstractmethod
    async def delete(self, profile_id: UUID) -> bool:
        """Delete research profile by ID."""
        pass

    @abstractmethod
    async def list_all(self, limit: int = 100, offset: int = 0) -> list[ResearchProfile]:
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
    async def get_stock_data(self, symbol: str, limit: int = 100) -> list[StockData]:
        """Get historical stock data."""
        pass
