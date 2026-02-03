"""Pytest configuration and fixtures."""

import tempfile
import warnings
from pathlib import Path

import pytest

# Suppress ResourceWarnings from yfinance/pandas/numpy internal SQLite caching
# These are from third-party libraries and not actionable for our code
warnings.filterwarnings("ignore", category=ResourceWarning, message=".*unclosed.*")
warnings.filterwarnings("ignore", category=ResourceWarning)

from copinanceos.domain.ports.data_providers import FundamentalDataProvider
from copinanceos.domain.ports.repositories import (
    ResearchProfileRepository,
    StockRepository,
)
from copinanceos.domain.ports.storage import Storage
from copinanceos.infrastructure.data_providers.yfinance import (
    YFinanceFundamentalProvider,
)
from copinanceos.infrastructure.repositories import (
    ResearchProfileRepositoryImpl,
    StockRepositoryImpl,
)
from copinanceos.infrastructure.repositories.storage.factory import create_storage


@pytest.fixture
def isolated_storage() -> Storage:
    """Provide isolated storage for each test using a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = create_storage(base_path=Path(tmpdir))
        yield storage
        # Storage is automatically cleaned up when tmpdir is deleted


@pytest.fixture
def profile_repository(isolated_storage: Storage) -> ResearchProfileRepository:
    """Provide a clean research profile repository for testing."""
    return ResearchProfileRepositoryImpl(storage=isolated_storage)


@pytest.fixture
def stock_repository(isolated_storage: Storage) -> StockRepository:
    """Provide a clean stock repository for testing."""
    return StockRepositoryImpl(storage=isolated_storage)


@pytest.fixture
def fundamental_data_provider() -> FundamentalDataProvider:
    """Provide a fundamental data provider for testing."""
    return YFinanceFundamentalProvider()
