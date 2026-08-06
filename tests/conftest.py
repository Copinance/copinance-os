"""Pytest configuration and fixtures."""

import warnings

import pytest

# Suppress ResourceWarnings from yfinance/pandas/numpy internal SQLite caching
# These are from third-party libraries and not actionable for our code
warnings.filterwarnings("ignore", category=ResourceWarning, message=".*unclosed.*")
warnings.filterwarnings("ignore", category=ResourceWarning)

from copinance_os.data.providers.yfinance import (
    YFinanceFundamentalProvider,
)
from copinance_os.data.repositories import (
    AnalysisProfileRepositoryImpl,
    StockRepositoryImpl,
)
from copinance_os.data.repositories.storage.memory import InMemoryStorage
from copinance_os.domain.ports.data_providers import FundamentalDataProvider
from copinance_os.domain.ports.repositories import (
    AnalysisProfileRepository,
    StockRepository,
)
from copinance_os.domain.ports.storage import Storage


@pytest.fixture
def isolated_storage() -> Storage:
    """Provide side-effect-free isolated storage for each test."""
    return InMemoryStorage()


@pytest.fixture
def profile_repository(isolated_storage: Storage) -> AnalysisProfileRepository:
    """Provide a clean analysis profile repository for testing."""
    return AnalysisProfileRepositoryImpl(storage=isolated_storage)


@pytest.fixture
def stock_repository(isolated_storage: Storage) -> StockRepository:
    """Provide a clean stock repository for testing."""
    return StockRepositoryImpl(storage=isolated_storage)


@pytest.fixture
def fundamental_data_provider() -> FundamentalDataProvider:
    """Provide a fundamental data provider for testing."""
    return YFinanceFundamentalProvider()
