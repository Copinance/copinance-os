"""Unit tests for market regime indicators tool."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from copinanceos.domain.models.stock import StockData
from copinanceos.domain.ports.data_providers import MarketDataProvider
from copinanceos.infrastructure.tools.analysis.market_regime.indicators import (
    SECTOR_ETFS,
    MarketRegimeIndicatorsTool,
    create_market_regime_indicators_tool,
)


@pytest.fixture
def mock_market_data_provider() -> MarketDataProvider:
    """Create a mock market data provider."""
    provider = MagicMock(spec=MarketDataProvider)
    provider.get_provider_name = MagicMock(return_value="test_provider")
    return provider


@pytest.fixture
def sample_vix_data() -> list[StockData]:
    """Create sample VIX data for testing."""
    base_date = datetime(2024, 1, 1)
    # VIX typically ranges from 10-30, with spikes up to 50+
    vix_levels = [12.5, 13.0, 14.2, 15.1, 16.0, 15.5, 14.8, 13.9, 13.2, 12.8]

    data = []
    for i, level in enumerate(vix_levels):
        data.append(
            StockData(
                symbol="^VIX",
                timestamp=base_date + timedelta(days=i),
                open_price=Decimal(str(level - 0.5)),
                close_price=Decimal(str(level)),
                high_price=Decimal(str(level + 0.5)),
                low_price=Decimal(str(level - 1.0)),
                volume=1000000,
            )
        )
    return data


@pytest.fixture
def sample_market_data() -> list[StockData]:
    """Create sample market index data (SPY) for testing."""
    base_date = datetime(2023, 1, 1)
    # Create upward trending market data
    data = []
    for i in range(252):
        price = 400.0 + (i * 0.5) + (i % 10) * 0.1
        data.append(
            StockData(
                symbol="SPY",
                timestamp=base_date + timedelta(days=i),
                open_price=Decimal(str(price - 0.5)),
                close_price=Decimal(str(price)),
                high_price=Decimal(str(price + 0.5)),
                low_price=Decimal(str(price - 1.0)),
                volume=100000000,
            )
        )
    return data


@pytest.fixture
def sample_sector_data() -> list[StockData]:
    """Create sample sector ETF data for testing."""
    base_date = datetime(2023, 1, 1)
    data = []
    for i in range(252):
        # Varying sector performance
        price = 100.0 + (i * 0.3) + (i % 20) * 0.2
        data.append(
            StockData(
                symbol="XLK",  # Technology sector
                timestamp=base_date + timedelta(days=i),
                open_price=Decimal(str(price - 0.5)),
                close_price=Decimal(str(price)),
                high_price=Decimal(str(price + 0.5)),
                low_price=Decimal(str(price - 1.0)),
                volume=10000000,
            )
        )
    return data


@pytest.mark.unit
class TestMarketRegimeIndicatorsTool:
    """Test MarketRegimeIndicatorsTool."""

    def test_initialization(self, mock_market_data_provider: MarketDataProvider) -> None:
        """Test tool initialization."""
        tool = MarketRegimeIndicatorsTool(mock_market_data_provider)
        assert tool._provider == mock_market_data_provider

    def test_get_name(self, mock_market_data_provider: MarketDataProvider) -> None:
        """Test tool name."""
        tool = MarketRegimeIndicatorsTool(mock_market_data_provider)
        assert tool.get_name() == "get_market_regime_indicators"

    def test_get_description(self, mock_market_data_provider: MarketDataProvider) -> None:
        """Test tool description."""
        tool = MarketRegimeIndicatorsTool(mock_market_data_provider)
        description = tool.get_description()
        assert "vix" in description.lower() or "volatility" in description.lower()
        assert "market breadth" in description.lower() or "breadth" in description.lower()
        assert "sector rotation" in description.lower() or "rotation" in description.lower()

    def test_get_schema(self, mock_market_data_provider: MarketDataProvider) -> None:
        """Test tool schema."""
        tool = MarketRegimeIndicatorsTool(mock_market_data_provider)
        schema = tool.get_schema()

        assert schema.name == "get_market_regime_indicators"
        assert "market_index" in schema.parameters["properties"]
        assert "lookback_days" in schema.parameters["properties"]
        assert "include_vix" in schema.parameters["properties"]
        assert "include_market_breadth" in schema.parameters["properties"]
        assert "include_sector_rotation" in schema.parameters["properties"]
        assert schema.parameters["properties"]["market_index"]["default"] == "SPY"
        assert schema.parameters["properties"]["lookback_days"]["default"] == 252

    @pytest.mark.asyncio
    async def test_execute_all_indicators(
        self,
        mock_market_data_provider: MarketDataProvider,
        sample_vix_data: list[StockData],
        sample_market_data: list[StockData],
        sample_sector_data: list[StockData],
    ) -> None:
        """Test successful execution with all indicators enabled."""

        # Mock provider to return different data based on symbol
        async def mock_get_historical_data(symbol, start_date, end_date, interval="1d"):
            if symbol == "^VIX":
                return sample_vix_data
            elif symbol == "SPY":
                return sample_market_data
            elif symbol in SECTOR_ETFS:
                return sample_sector_data
            return []

        mock_market_data_provider.get_historical_data = AsyncMock(
            side_effect=mock_get_historical_data
        )

        tool = MarketRegimeIndicatorsTool(mock_market_data_provider)
        result = await tool.execute(market_index="SPY", lookback_days=252)

        assert result.success is True
        assert result.data["market_index"] == "SPY"
        assert result.data["lookback_days"] == 252
        assert "analysis_date" in result.data
        assert "vix" in result.data
        assert "market_breadth" in result.data
        assert "sector_rotation" in result.data

    @pytest.mark.asyncio
    async def test_execute_vix_only(
        self,
        mock_market_data_provider: MarketDataProvider,
        sample_vix_data: list[StockData],
    ) -> None:
        """Test execution with only VIX indicator."""
        mock_market_data_provider.get_historical_data = AsyncMock(return_value=sample_vix_data)

        tool = MarketRegimeIndicatorsTool(mock_market_data_provider)
        result = await tool.execute(
            market_index="SPY",
            include_vix=True,
            include_market_breadth=False,
            include_sector_rotation=False,
        )

        assert result.success is True
        assert "vix" in result.data
        assert "market_breadth" not in result.data
        assert "sector_rotation" not in result.data

    @pytest.mark.asyncio
    async def test_execute_market_breadth_only(
        self,
        mock_market_data_provider: MarketDataProvider,
        sample_market_data: list[StockData],
        sample_sector_data: list[StockData],
    ) -> None:
        """Test execution with only market breadth indicator."""

        async def mock_get_historical_data(symbol, start_date, end_date, interval="1d"):
            if symbol == "SPY":
                return sample_market_data
            elif symbol in SECTOR_ETFS:
                return sample_sector_data
            return []

        mock_market_data_provider.get_historical_data = AsyncMock(
            side_effect=mock_get_historical_data
        )

        tool = MarketRegimeIndicatorsTool(mock_market_data_provider)
        result = await tool.execute(
            market_index="SPY",
            include_vix=False,
            include_market_breadth=True,
            include_sector_rotation=False,
        )

        assert result.success is True
        assert "vix" not in result.data
        assert "market_breadth" in result.data
        assert "sector_rotation" not in result.data

    @pytest.mark.asyncio
    async def test_execute_sector_rotation_only(
        self,
        mock_market_data_provider: MarketDataProvider,
        sample_market_data: list[StockData],
        sample_sector_data: list[StockData],
    ) -> None:
        """Test execution with only sector rotation indicator."""

        async def mock_get_historical_data(symbol, start_date, end_date, interval="1d"):
            if symbol == "SPY":
                return sample_market_data
            elif symbol in SECTOR_ETFS:
                return sample_sector_data
            return []

        mock_market_data_provider.get_historical_data = AsyncMock(
            side_effect=mock_get_historical_data
        )

        tool = MarketRegimeIndicatorsTool(mock_market_data_provider)
        result = await tool.execute(
            market_index="SPY",
            include_vix=False,
            include_market_breadth=False,
            include_sector_rotation=True,
        )

        assert result.success is True
        assert "vix" not in result.data
        assert "market_breadth" not in result.data
        assert "sector_rotation" in result.data

    @pytest.mark.asyncio
    async def test_fetch_vix_data_success(
        self,
        mock_market_data_provider: MarketDataProvider,
        sample_vix_data: list[StockData],
    ) -> None:
        """Test successful VIX data fetching."""
        mock_market_data_provider.get_historical_data = AsyncMock(return_value=sample_vix_data)

        tool = MarketRegimeIndicatorsTool(mock_market_data_provider)
        vix_data = await tool._fetch_vix_data(datetime(2024, 1, 1), datetime(2024, 1, 10))

        assert vix_data["available"] is True
        assert "current_vix" in vix_data
        assert "recent_average_20d" in vix_data
        assert "regime" in vix_data
        assert "sentiment" in vix_data
        assert vix_data["regime"] in ["low", "normal", "high", "very_high"]
        assert vix_data["sentiment"] in ["complacent", "normal", "fearful", "panic"]

    @pytest.mark.asyncio
    async def test_fetch_vix_data_no_data(
        self, mock_market_data_provider: MarketDataProvider
    ) -> None:
        """Test VIX data fetching with no data available."""
        mock_market_data_provider.get_historical_data = AsyncMock(return_value=[])

        tool = MarketRegimeIndicatorsTool(mock_market_data_provider)
        vix_data = await tool._fetch_vix_data(datetime(2024, 1, 1), datetime(2024, 1, 10))

        assert vix_data["available"] is False
        assert "error" in vix_data

    @pytest.mark.asyncio
    async def test_fetch_vix_data_high_volatility(
        self, mock_market_data_provider: MarketDataProvider
    ) -> None:
        """Test VIX data with high volatility levels."""
        base_date = datetime(2024, 1, 1)
        high_vix_data = [
            StockData(
                symbol="^VIX",
                timestamp=base_date + timedelta(days=i),
                open_price=Decimal("28.0"),
                close_price=Decimal("32.0"),  # High VIX
                high_price=Decimal("33.0"),
                low_price=Decimal("27.0"),
                volume=1000000,
            )
            for i in range(20)
        ]

        mock_market_data_provider.get_historical_data = AsyncMock(return_value=high_vix_data)

        tool = MarketRegimeIndicatorsTool(mock_market_data_provider)
        vix_data = await tool._fetch_vix_data(datetime(2024, 1, 1), datetime(2024, 1, 20))

        assert vix_data["available"] is True
        assert vix_data["regime"] in ["high", "very_high"]
        assert vix_data["sentiment"] in ["fearful", "panic"]

    @pytest.mark.asyncio
    async def test_calculate_market_breadth_success(
        self,
        mock_market_data_provider: MarketDataProvider,
        sample_market_data: list[StockData],
        sample_sector_data: list[StockData],
    ) -> None:
        """Test successful market breadth calculation."""

        async def mock_get_historical_data(symbol, start_date, end_date, interval="1d"):
            if symbol == "SPY":
                return sample_market_data
            elif symbol in SECTOR_ETFS:
                return sample_sector_data
            return []

        mock_market_data_provider.get_historical_data = AsyncMock(
            side_effect=mock_get_historical_data
        )

        tool = MarketRegimeIndicatorsTool(mock_market_data_provider)
        breadth_data = await tool._calculate_market_breadth(
            "SPY", datetime(2023, 1, 1), datetime(2023, 12, 31)
        )

        assert breadth_data["available"] is True
        assert "breadth_ratio" in breadth_data
        assert "participation_ratio" in breadth_data
        assert "sectors_above_50ma" in breadth_data
        assert "sectors_outperforming" in breadth_data
        assert "total_sectors_analyzed" in breadth_data
        assert "regime" in breadth_data
        assert breadth_data["regime"] in ["strong", "moderate", "weak"]
        assert "sector_details" in breadth_data

    @pytest.mark.asyncio
    async def test_calculate_market_breadth_no_market_data(
        self, mock_market_data_provider: MarketDataProvider
    ) -> None:
        """Test market breadth calculation with no market data."""
        mock_market_data_provider.get_historical_data = AsyncMock(return_value=[])

        tool = MarketRegimeIndicatorsTool(mock_market_data_provider)
        breadth_data = await tool._calculate_market_breadth(
            "SPY", datetime(2023, 1, 1), datetime(2023, 12, 31)
        )

        assert breadth_data["available"] is False
        assert "error" in breadth_data

    @pytest.mark.asyncio
    async def test_calculate_sector_rotation_success(
        self,
        mock_market_data_provider: MarketDataProvider,
        sample_market_data: list[StockData],
        sample_sector_data: list[StockData],
    ) -> None:
        """Test successful sector rotation calculation."""

        async def mock_get_historical_data(symbol, start_date, end_date, interval="1d"):
            if symbol == "SPY":
                return sample_market_data
            elif symbol in SECTOR_ETFS:
                return sample_sector_data
            return []

        mock_market_data_provider.get_historical_data = AsyncMock(
            side_effect=mock_get_historical_data
        )

        tool = MarketRegimeIndicatorsTool(mock_market_data_provider)
        rotation_data = await tool._calculate_sector_rotation(
            "SPY", datetime(2023, 1, 1), datetime(2023, 12, 31)
        )

        assert rotation_data["available"] is True
        assert "rotation_theme" in rotation_data
        assert rotation_data["rotation_theme"] in ["defensive", "growth", "value", "mixed"]
        assert "leading_sectors" in rotation_data
        assert "lagging_sectors" in rotation_data
        assert "all_sectors_ranked" in rotation_data
        assert "market_return_20d" in rotation_data
        assert "market_return_60d" in rotation_data

    @pytest.mark.asyncio
    async def test_calculate_sector_rotation_no_data(
        self, mock_market_data_provider: MarketDataProvider
    ) -> None:
        """Test sector rotation calculation with no data."""
        mock_market_data_provider.get_historical_data = AsyncMock(return_value=[])

        tool = MarketRegimeIndicatorsTool(mock_market_data_provider)
        rotation_data = await tool._calculate_sector_rotation(
            "SPY", datetime(2023, 1, 1), datetime(2023, 12, 31)
        )

        assert rotation_data["available"] is False
        assert "error" in rotation_data

    @pytest.mark.asyncio
    async def test_execute_exception_handling(
        self, mock_market_data_provider: MarketDataProvider
    ) -> None:
        """Test tool handles exceptions gracefully."""
        mock_market_data_provider.get_historical_data = AsyncMock(
            side_effect=Exception("Provider error")
        )

        tool = MarketRegimeIndicatorsTool(mock_market_data_provider)
        result = await tool.execute(market_index="SPY")

        # The tool catches exceptions in individual methods and returns error dicts
        # So the overall result is successful, but individual indicators have errors
        assert result.success is True
        # Check that indicators have errors (all are included by default)
        assert "vix" in result.data
        assert result.data["vix"]["available"] is False
        assert "error" in result.data["vix"]
        assert "market_breadth" in result.data
        assert result.data["market_breadth"]["available"] is False
        assert "error" in result.data["market_breadth"]
        assert "sector_rotation" in result.data
        assert result.data["sector_rotation"]["available"] is False
        assert "error" in result.data["sector_rotation"]

    @pytest.mark.asyncio
    async def test_execute_custom_market_index(
        self,
        mock_market_data_provider: MarketDataProvider,
        sample_market_data: list[StockData],
    ) -> None:
        """Test execution with custom market index."""

        async def mock_get_historical_data(symbol, start_date, end_date, interval="1d"):
            if symbol == "QQQ":
                return sample_market_data
            return []

        mock_market_data_provider.get_historical_data = AsyncMock(
            side_effect=mock_get_historical_data
        )

        tool = MarketRegimeIndicatorsTool(mock_market_data_provider)
        result = await tool.execute(
            market_index="QQQ",
            include_vix=False,
            include_market_breadth=False,
            include_sector_rotation=False,
        )

        assert result.success is True
        assert result.data["market_index"] == "QQQ"

    @pytest.mark.asyncio
    async def test_execute_custom_lookback_days(
        self,
        mock_market_data_provider: MarketDataProvider,
        sample_vix_data: list[StockData],
    ) -> None:
        """Test execution with custom lookback days."""
        mock_market_data_provider.get_historical_data = AsyncMock(return_value=sample_vix_data)

        tool = MarketRegimeIndicatorsTool(mock_market_data_provider)
        result = await tool.execute(
            market_index="SPY",
            lookback_days=100,
            include_vix=True,
            include_market_breadth=False,
            include_sector_rotation=False,
        )

        assert result.success is True
        assert result.data["lookback_days"] == 100


@pytest.mark.unit
class TestFactoryFunction:
    """Test factory function for creating indicators tool."""

    def test_create_market_regime_indicators_tool(
        self, mock_market_data_provider: MarketDataProvider
    ) -> None:
        """Test creating market regime indicators tool."""
        tool = create_market_regime_indicators_tool(mock_market_data_provider)

        assert isinstance(tool, MarketRegimeIndicatorsTool)
        assert tool._provider == mock_market_data_provider
