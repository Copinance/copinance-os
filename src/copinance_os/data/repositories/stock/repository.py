"""Equity instrument repository implementation."""

from copinance_os.data.repositories.storage.factory import create_storage
from copinance_os.domain.models.market import MarketDataPoint
from copinance_os.domain.models.stock import Stock
from copinance_os.domain.ports.repositories import StockRepository
from copinance_os.domain.ports.storage import Storage


class StockRepositoryImpl(StockRepository):
    """Implementation of StockRepository.

    This repository uses the Storage interface, hiding the underlying
    storage implementation. The storage technology is not exposed
    to consumers of this repository.
    """

    def __init__(self, storage: Storage | None = None) -> None:
        """Initialize repository.

        Args:
            storage: Optional storage backend. If None, creates default storage.
                     Should implement the Storage interface.
        """
        if storage is None:
            storage = create_storage()
        self._storage = storage
        self._stocks = self._storage.get_collection("market/instruments/equities", Stock)
        self._market_data: dict[str, list[MarketDataPoint]] = {}

    async def get_by_symbol(self, symbol: str) -> Stock | None:
        """Get stock by symbol."""
        # Find stock by symbol (stocks are keyed by UUID, need to search)
        for stock in self._stocks.values():
            # Type narrowing: storage returns dict[UUID, Any], but we know it's Stock
            if isinstance(stock, Stock) and stock.symbol.upper() == symbol.upper():
                return stock
        return None

    async def search(self, query: str, limit: int = 10) -> list[Stock]:
        """Search equity instruments by query."""
        query_lower = query.lower()
        results = [
            stock
            for stock in self._stocks.values()
            if query_lower in stock.symbol.lower() or query_lower in stock.name.lower()
        ]
        return results[:limit]

    async def save(self, stock: Stock) -> Stock:
        """Save or update equity instrument."""
        self._stocks[stock.id] = stock
        self._storage.save("market/instruments/equities")
        return stock

    async def get_market_data(self, symbol: str, limit: int = 100) -> list[MarketDataPoint]:
        """Get historical market data."""
        data = self._market_data.get(symbol.upper(), [])
        return data[:limit]
