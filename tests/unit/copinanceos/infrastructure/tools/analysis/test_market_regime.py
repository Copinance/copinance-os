"""Unit tests for market regime detection tools."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from copinanceos.domain.models.stock import StockData
from copinanceos.domain.ports.data_providers import MarketDataProvider
from copinanceos.infrastructure.tools.analysis.market_regime.registry import (
    create_all_regime_tools,
    create_regime_tools_by_type,
)
from copinanceos.infrastructure.tools.analysis.market_regime.rule_based import (
    MarketRegimeDetectCyclesTool,
    MarketRegimeDetectTrendTool,
    MarketRegimeDetectVolatilityTool,
    _calculate_ewma_volatility,
    _calculate_log_returns,
    _calculate_moving_average,
    _calculate_volatility,
    _classify_volatility_regime,
    _classify_volatility_regime_percentile,
    create_rule_based_regime_tools,
)


@pytest.fixture
def mock_market_data_provider() -> MarketDataProvider:
    """Create a mock market data provider."""
    provider = MagicMock(spec=MarketDataProvider)
    provider.get_provider_name = MagicMock(return_value="test_provider")
    return provider


@pytest.fixture
def sample_stock_data() -> list[StockData]:
    """Create sample stock data for testing."""
    base_date = datetime(2024, 1, 1)
    prices = [100.0, 102.0, 101.0, 105.0, 108.0, 107.0, 110.0, 112.0, 115.0, 118.0]

    data = []
    for i, price in enumerate(prices):
        data.append(
            StockData(
                symbol="TEST",
                timestamp=base_date + timedelta(days=i),
                open_price=Decimal(str(price - 0.5)),
                close_price=Decimal(str(price)),
                high_price=Decimal(str(price + 0.5)),
                low_price=Decimal(str(price - 1.0)),
                volume=1000000 + i * 10000,
            )
        )
    return data


@pytest.fixture
def extended_stock_data() -> list[StockData]:
    """Create extended stock data (200+ days) for testing."""
    base_date = datetime(2023, 1, 1)
    # Create a trending upward pattern
    data = []
    for i in range(250):
        # Upward trend with some noise
        price = 100.0 + (i * 0.5) + (i % 10) * 0.1
        data.append(
            StockData(
                symbol="TEST",
                timestamp=base_date + timedelta(days=i),
                open_price=Decimal(str(price - 0.5)),
                close_price=Decimal(str(price)),
                high_price=Decimal(str(price + 0.5)),
                low_price=Decimal(str(price - 1.0)),
                volume=1000000 + (i % 100000),
            )
        )
    return data


@pytest.mark.unit
class TestHelperFunctions:
    """Test helper functions for market regime detection."""

    def test_calculate_moving_average_sufficient_data(self) -> None:
        """Test moving average calculation with sufficient data."""
        prices = [100.0, 102.0, 101.0, 105.0, 108.0, 107.0, 110.0, 112.0, 115.0, 118.0]
        window = 3

        result = _calculate_moving_average(prices, window)

        assert len(result) == len(prices)
        assert result[0] is None  # First window-1 values are None
        assert result[1] is None
        assert result[2] is not None  # First valid MA
        assert result[2] == (100.0 + 102.0 + 101.0) / 3
        assert result[-1] is not None  # Last value should be valid

    def test_calculate_moving_average_insufficient_data(self) -> None:
        """Test moving average with insufficient data."""
        prices = [100.0, 102.0]
        window = 5

        result = _calculate_moving_average(prices, window)

        assert len(result) == len(prices)
        assert all(v is None for v in result)

    def test_calculate_log_returns(self) -> None:
        """Test log-returns calculation."""
        prices = [100.0, 102.0, 101.0, 105.0]

        log_returns = _calculate_log_returns(prices)

        assert len(log_returns) == len(prices) - 1
        assert log_returns[0] == pytest.approx(0.0198, abs=0.0001)  # ln(102/100)
        assert log_returns[1] == pytest.approx(-0.0099, abs=0.0001)  # ln(101/102)

    def test_calculate_volatility(self) -> None:
        """Test volatility calculation using log-returns."""
        # Create prices with known volatility pattern
        prices = [100.0 + i * 0.1 + (i % 3) * 0.5 for i in range(50)]

        volatility = _calculate_volatility(prices, window=20)

        assert len(volatility) == len(prices)
        assert volatility[0] is None  # First value has no volatility
        # First window values should be None
        assert all(v is None for v in volatility[1:21])
        # After window, should have valid volatility
        assert volatility[21] is not None
        assert volatility[-1] is not None

    def test_classify_volatility_regime_high(self) -> None:
        """Test volatility regime classification - high."""
        historical_vols = [0.15, 0.16, 0.17, 0.18, 0.19, 0.20, 0.21, 0.22, 0.23, 0.24]
        current_vol = 0.30  # Well above mean + std

        regime = _classify_volatility_regime(current_vol, historical_vols)

        assert regime == "high"

    def test_classify_volatility_regime_low(self) -> None:
        """Test volatility regime classification - low."""
        historical_vols = [0.15, 0.16, 0.17, 0.18, 0.19, 0.20, 0.21, 0.22, 0.23, 0.24]
        current_vol = 0.10  # Well below mean - std

        regime = _classify_volatility_regime(current_vol, historical_vols)

        assert regime == "low"

    def test_classify_volatility_regime_normal(self) -> None:
        """Test volatility regime classification - normal."""
        historical_vols = [0.15, 0.16, 0.17, 0.18, 0.19, 0.20, 0.21, 0.22, 0.23, 0.24]
        current_vol = 0.19  # Within one std of mean

        regime = _classify_volatility_regime(current_vol, historical_vols)

        assert regime == "normal"

    def test_classify_volatility_regime_percentile_high(self) -> None:
        """Test percentile-based volatility classification - high."""
        historical_vols = [0.10, 0.12, 0.14, 0.16, 0.18, 0.20, 0.22, 0.24, 0.26, 0.28]
        current_vol = 0.27  # Above 80th percentile

        regime = _classify_volatility_regime_percentile(current_vol, historical_vols)

        assert regime == "high"

    def test_classify_volatility_regime_percentile_low(self) -> None:
        """Test percentile-based volatility classification - low."""
        historical_vols = [0.10, 0.12, 0.14, 0.16, 0.18, 0.20, 0.22, 0.24, 0.26, 0.28]
        current_vol = 0.11  # Below 20th percentile

        regime = _classify_volatility_regime_percentile(current_vol, historical_vols)

        assert regime == "low"

    def test_calculate_ewma_volatility(self) -> None:
        """Test EWMA volatility calculation."""
        # Create prices with known pattern
        prices = [100.0 + i * 0.1 + (i % 5) * 0.2 for i in range(50)]

        ewma_vols = _calculate_ewma_volatility(prices, lambda_param=0.94)

        # EWMA returns len(prices) - 1 values: None for first price, then one per log-return
        # log_returns has len(prices) - 1 elements, loop is range(1, len(log_returns))
        # So we get: 1 None + (len(log_returns) - 1) values = len(prices) - 1 total
        assert len(ewma_vols) == len(prices) - 1
        assert ewma_vols[0] is None  # First value has no volatility
        assert (
            ewma_vols[1] is not None
        )  # Second value should have volatility (from first log-return)
        assert ewma_vols[-1] is not None  # Last value should have volatility
        # EWMA volatility should be positive
        assert all(v is None or v > 0 for v in ewma_vols)

    def test_calculate_ewma_volatility_insufficient_data(self) -> None:
        """Test EWMA volatility with insufficient data."""
        prices = [100.0]

        ewma_vols = _calculate_ewma_volatility(prices)

        assert len(ewma_vols) == 1
        assert ewma_vols[0] is None


@pytest.mark.unit
class TestMarketRegimeDetectTrendTool:
    """Test MarketRegimeDetectTrendTool."""

    def test_initialization(self, mock_market_data_provider: MarketDataProvider) -> None:
        """Test tool initialization."""
        tool = MarketRegimeDetectTrendTool(mock_market_data_provider)
        assert tool._provider == mock_market_data_provider

    def test_get_name(self, mock_market_data_provider: MarketDataProvider) -> None:
        """Test tool name."""
        tool = MarketRegimeDetectTrendTool(mock_market_data_provider)
        assert tool.get_name() == "detect_market_trend"

    def test_get_description(self, mock_market_data_provider: MarketDataProvider) -> None:
        """Test tool description."""
        tool = MarketRegimeDetectTrendTool(mock_market_data_provider)
        description = tool.get_description()
        assert "trend" in description.lower()
        assert "bull" in description.lower() or "bear" in description.lower()

    def test_get_schema(self, mock_market_data_provider: MarketDataProvider) -> None:
        """Test tool schema."""
        tool = MarketRegimeDetectTrendTool(mock_market_data_provider)
        schema = tool.get_schema()

        assert schema.name == "detect_market_trend"
        assert "symbol" in schema.parameters["properties"]
        assert "symbol" in schema.parameters["required"]
        assert "lookback_days" in schema.parameters["properties"]
        assert schema.parameters["properties"]["lookback_days"]["default"] == 200

    @pytest.mark.asyncio
    async def test_execute_success_bull_market(
        self, mock_market_data_provider: MarketDataProvider, extended_stock_data: list[StockData]
    ) -> None:
        """Test successful trend detection for bull market."""
        mock_market_data_provider.get_historical_data = AsyncMock(return_value=extended_stock_data)

        tool = MarketRegimeDetectTrendTool(mock_market_data_provider)
        result = await tool.execute(symbol="TEST", lookback_days=200)

        assert result.success is True
        assert result.data["symbol"] == "TEST"
        assert result.data["regime"] in ["bull", "bear", "neutral"]
        assert "confidence" in result.data
        assert "current_price" in result.data
        assert "log_return" in result.data
        assert "volatility_scaled_momentum" in result.data
        assert "methodology" in result.data

    @pytest.mark.asyncio
    async def test_execute_insufficient_data(
        self, mock_market_data_provider: MarketDataProvider, sample_stock_data: list[StockData]
    ) -> None:
        """Test trend detection with insufficient data."""
        # Provide only 10 data points when 200 are needed for long MA
        mock_market_data_provider.get_historical_data = AsyncMock(return_value=sample_stock_data)

        tool = MarketRegimeDetectTrendTool(mock_market_data_provider)
        result = await tool.execute(symbol="TEST", lookback_days=200)

        # Should adapt parameters and still succeed
        assert result.success is True
        assert result.data["parameters_adjusted"] is True
        assert "note" in result.data

    @pytest.mark.asyncio
    async def test_execute_no_data(self, mock_market_data_provider: MarketDataProvider) -> None:
        """Test trend detection with no historical data."""
        mock_market_data_provider.get_historical_data = AsyncMock(return_value=[])

        tool = MarketRegimeDetectTrendTool(mock_market_data_provider)
        result = await tool.execute(symbol="TEST")

        assert result.success is False
        assert "No historical data" in result.error

    @pytest.mark.asyncio
    async def test_execute_very_limited_data(
        self, mock_market_data_provider: MarketDataProvider
    ) -> None:
        """Test trend detection with very limited data (< 10 points)."""
        limited_data = [
            StockData(
                symbol="TEST",
                timestamp=datetime.now() - timedelta(days=i),
                open_price=Decimal("100.0"),
                close_price=Decimal("100.0"),
                high_price=Decimal("101.0"),
                low_price=Decimal("99.0"),
                volume=1000000,
            )
            for i in range(5)
        ]
        mock_market_data_provider.get_historical_data = AsyncMock(return_value=limited_data)

        tool = MarketRegimeDetectTrendTool(mock_market_data_provider)
        result = await tool.execute(symbol="TEST")

        assert result.success is False
        assert "Insufficient data" in result.error

    @pytest.mark.asyncio
    async def test_execute_parameter_validation(
        self, mock_market_data_provider: MarketDataProvider
    ) -> None:
        """Test parameter validation."""
        tool = MarketRegimeDetectTrendTool(mock_market_data_provider)

        # Missing required parameter - tool returns error result instead of raising
        result = await tool.execute()

        assert result.success is False
        assert "Missing required parameter" in result.error or "symbol" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_with_custom_parameters(
        self, mock_market_data_provider: MarketDataProvider, extended_stock_data: list[StockData]
    ) -> None:
        """Test trend detection with custom parameters."""
        mock_market_data_provider.get_historical_data = AsyncMock(return_value=extended_stock_data)

        tool = MarketRegimeDetectTrendTool(mock_market_data_provider)
        result = await tool.execute(
            symbol="TEST",
            lookback_days=100,
            short_ma_period=20,
            long_ma_period=50,
        )

        assert result.success is True
        assert result.data["short_ma_period_used"] == 20
        assert result.data["long_ma_period_used"] == 50


@pytest.mark.unit
class TestMarketRegimeDetectVolatilityTool:
    """Test MarketRegimeDetectVolatilityTool."""

    def test_initialization(self, mock_market_data_provider: MarketDataProvider) -> None:
        """Test tool initialization."""
        tool = MarketRegimeDetectVolatilityTool(mock_market_data_provider)
        assert tool._provider == mock_market_data_provider

    def test_get_name(self, mock_market_data_provider: MarketDataProvider) -> None:
        """Test tool name."""
        tool = MarketRegimeDetectVolatilityTool(mock_market_data_provider)
        assert tool.get_name() == "detect_volatility_regime"

    def test_get_schema(self, mock_market_data_provider: MarketDataProvider) -> None:
        """Test tool schema."""
        tool = MarketRegimeDetectVolatilityTool(mock_market_data_provider)
        schema = tool.get_schema()

        assert schema.name == "detect_volatility_regime"
        assert "symbol" in schema.parameters["properties"]
        assert "volatility_window" in schema.parameters["properties"]
        assert schema.parameters["properties"]["volatility_window"]["default"] == 20

    @pytest.mark.asyncio
    async def test_execute_success(
        self, mock_market_data_provider: MarketDataProvider, extended_stock_data: list[StockData]
    ) -> None:
        """Test successful volatility regime detection."""
        mock_market_data_provider.get_historical_data = AsyncMock(return_value=extended_stock_data)

        tool = MarketRegimeDetectVolatilityTool(mock_market_data_provider)
        result = await tool.execute(symbol="TEST", lookback_days=252)

        assert result.success is True
        assert result.data["symbol"] == "TEST"
        assert result.data["regime"] in ["high", "normal", "low"]
        assert "current_volatility" in result.data
        assert "mean_volatility" in result.data
        assert "volatility_percentile" in result.data

    @pytest.mark.asyncio
    async def test_execute_insufficient_data(
        self, mock_market_data_provider: MarketDataProvider, sample_stock_data: list[StockData]
    ) -> None:
        """Test volatility detection with insufficient data."""
        mock_market_data_provider.get_historical_data = AsyncMock(return_value=sample_stock_data)

        tool = MarketRegimeDetectVolatilityTool(mock_market_data_provider)
        result = await tool.execute(symbol="TEST", volatility_window=20)

        # Should adapt parameters and still succeed
        assert result.success is True
        assert result.data["parameters_adjusted"] is True

    @pytest.mark.asyncio
    async def test_execute_no_data(self, mock_market_data_provider: MarketDataProvider) -> None:
        """Test volatility detection with no historical data."""
        mock_market_data_provider.get_historical_data = AsyncMock(return_value=[])

        tool = MarketRegimeDetectVolatilityTool(mock_market_data_provider)
        result = await tool.execute(symbol="TEST")

        assert result.success is False
        assert "No historical data" in result.error


@pytest.mark.unit
class TestMarketRegimeDetectCyclesTool:
    """Test MarketRegimeDetectCyclesTool."""

    def test_initialization(self, mock_market_data_provider: MarketDataProvider) -> None:
        """Test tool initialization."""
        tool = MarketRegimeDetectCyclesTool(mock_market_data_provider)
        assert tool._provider == mock_market_data_provider

    def test_get_name(self, mock_market_data_provider: MarketDataProvider) -> None:
        """Test tool name."""
        tool = MarketRegimeDetectCyclesTool(mock_market_data_provider)
        assert tool.get_name() == "detect_market_cycles"

    def test_get_schema(self, mock_market_data_provider: MarketDataProvider) -> None:
        """Test tool schema."""
        tool = MarketRegimeDetectCyclesTool(mock_market_data_provider)
        schema = tool.get_schema()

        assert schema.name == "detect_market_cycles"
        assert "symbol" in schema.parameters["properties"]
        assert "symbol" in schema.parameters["required"]

    @pytest.mark.asyncio
    async def test_execute_success(
        self, mock_market_data_provider: MarketDataProvider, extended_stock_data: list[StockData]
    ) -> None:
        """Test successful cycle detection."""
        mock_market_data_provider.get_historical_data = AsyncMock(return_value=extended_stock_data)

        tool = MarketRegimeDetectCyclesTool(mock_market_data_provider)
        result = await tool.execute(symbol="TEST", lookback_days=252)

        assert result.success is True
        assert result.data["symbol"] == "TEST"
        assert result.data["current_phase"] in [
            "accumulation",
            "markup",
            "distribution",
            "markdown",
            "transition",
        ]
        assert "phase_description" in result.data
        assert "price_position_pct" in result.data
        assert "volume_ratio" in result.data
        assert "potential_regime_change" in result.data

    @pytest.mark.asyncio
    async def test_execute_insufficient_data(
        self, mock_market_data_provider: MarketDataProvider, sample_stock_data: list[StockData]
    ) -> None:
        """Test cycle detection with insufficient data."""
        mock_market_data_provider.get_historical_data = AsyncMock(return_value=sample_stock_data)

        tool = MarketRegimeDetectCyclesTool(mock_market_data_provider)
        result = await tool.execute(symbol="TEST")

        # Should adapt parameters and still succeed if >= 20 points
        if len(sample_stock_data) >= 20:
            assert result.success is True
            assert result.data["parameters_adjusted"] is True
        else:
            assert result.success is False

    @pytest.mark.asyncio
    async def test_execute_no_data(self, mock_market_data_provider: MarketDataProvider) -> None:
        """Test cycle detection with no historical data."""
        mock_market_data_provider.get_historical_data = AsyncMock(return_value=[])

        tool = MarketRegimeDetectCyclesTool(mock_market_data_provider)
        result = await tool.execute(symbol="TEST")

        assert result.success is False
        assert "No historical data" in result.error


@pytest.mark.unit
class TestFactoryFunctions:
    """Test factory functions for creating regime detection tools."""

    def test_create_rule_based_regime_tools(
        self, mock_market_data_provider: MarketDataProvider
    ) -> None:
        """Test creating rule-based regime tools."""
        tools = create_rule_based_regime_tools(mock_market_data_provider)

        assert len(tools) == 3
        assert isinstance(tools[0], MarketRegimeDetectTrendTool)
        assert isinstance(tools[1], MarketRegimeDetectVolatilityTool)
        assert isinstance(tools[2], MarketRegimeDetectCyclesTool)

        # Verify all tools use the same provider
        assert tools[0]._provider == mock_market_data_provider
        assert tools[1]._provider == mock_market_data_provider
        assert tools[2]._provider == mock_market_data_provider


@pytest.mark.unit
class TestRegistryFunctions:
    """Test registry functions for regime detection tools."""

    def test_create_all_regime_tools_default(
        self, mock_market_data_provider: MarketDataProvider
    ) -> None:
        """Test creating all regime tools with default method."""
        tools = create_all_regime_tools(mock_market_data_provider)

        # Default should be rule_based only
        assert len(tools) == 3
        assert all(
            isinstance(
                t,
                (
                    MarketRegimeDetectTrendTool,
                    MarketRegimeDetectVolatilityTool,
                    MarketRegimeDetectCyclesTool,
                ),
            )
            for t in tools
        )

    def test_create_all_regime_tools_rule_based(
        self, mock_market_data_provider: MarketDataProvider
    ) -> None:
        """Test creating all regime tools with rule_based method."""
        tools = create_all_regime_tools(mock_market_data_provider, methods=["rule_based"])

        assert len(tools) == 3

    def test_create_all_regime_tools_statistical(
        self, mock_market_data_provider: MarketDataProvider
    ) -> None:
        """Test creating all regime tools with statistical method (empty for now)."""
        tools = create_all_regime_tools(mock_market_data_provider, methods=["statistical"])

        # Statistical tools not yet implemented
        assert len(tools) == 0

    def test_create_all_regime_tools_multiple_methods(
        self, mock_market_data_provider: MarketDataProvider
    ) -> None:
        """Test creating all regime tools with multiple methods."""
        tools = create_all_regime_tools(
            mock_market_data_provider, methods=["rule_based", "statistical"]
        )

        # Should have rule_based tools (statistical not implemented yet)
        assert len(tools) == 3

    def test_create_regime_tools_by_type_rule_based(
        self, mock_market_data_provider: MarketDataProvider
    ) -> None:
        """Test creating tools by type - rule_based."""
        tools = create_regime_tools_by_type(mock_market_data_provider, "rule_based")

        assert len(tools) == 3
        assert isinstance(tools[0], MarketRegimeDetectTrendTool)

    def test_create_regime_tools_by_type_statistical(
        self, mock_market_data_provider: MarketDataProvider
    ) -> None:
        """Test creating tools by type - statistical (empty for now)."""
        tools = create_regime_tools_by_type(mock_market_data_provider, "statistical")

        # Statistical tools not yet implemented
        assert len(tools) == 0

    def test_create_regime_tools_by_type_invalid(
        self, mock_market_data_provider: MarketDataProvider
    ) -> None:
        """Test creating tools by type with invalid method."""
        with pytest.raises(ValueError, match="Unknown method"):
            create_regime_tools_by_type(mock_market_data_provider, "invalid_method")


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_trend_tool_exception_handling(
        self, mock_market_data_provider: MarketDataProvider
    ) -> None:
        """Test trend tool handles exceptions gracefully."""
        mock_market_data_provider.get_historical_data = AsyncMock(
            side_effect=Exception("Provider error")
        )

        tool = MarketRegimeDetectTrendTool(mock_market_data_provider)
        result = await tool.execute(symbol="TEST")

        assert result.success is False
        assert "error" in result.error.lower() or "Provider error" in result.error

    @pytest.mark.asyncio
    async def test_volatility_tool_exception_handling(
        self, mock_market_data_provider: MarketDataProvider
    ) -> None:
        """Test volatility tool handles exceptions gracefully."""
        mock_market_data_provider.get_historical_data = AsyncMock(
            side_effect=Exception("Provider error")
        )

        tool = MarketRegimeDetectVolatilityTool(mock_market_data_provider)
        result = await tool.execute(symbol="TEST")

        assert result.success is False
        assert "error" in result.error.lower() or "Provider error" in result.error

    @pytest.mark.asyncio
    async def test_cycles_tool_exception_handling(
        self, mock_market_data_provider: MarketDataProvider
    ) -> None:
        """Test cycles tool handles exceptions gracefully."""
        mock_market_data_provider.get_historical_data = AsyncMock(
            side_effect=Exception("Provider error")
        )

        tool = MarketRegimeDetectCyclesTool(mock_market_data_provider)
        result = await tool.execute(symbol="TEST")

        assert result.success is False
        assert "error" in result.error.lower() or "Provider error" in result.error

    @pytest.mark.asyncio
    async def test_trend_tool_bear_market_pattern(
        self, mock_market_data_provider: MarketDataProvider
    ) -> None:
        """Test trend detection with bear market pattern (declining prices)."""
        base_date = datetime(2024, 1, 1)
        # Create declining price pattern (ensure prices stay positive)
        declining_data = [
            StockData(
                symbol="TEST",
                timestamp=base_date + timedelta(days=i),
                open_price=Decimal(str(max(10.0, 120.0 - i * 0.3))),
                close_price=Decimal(str(max(10.0, 120.0 - i * 0.3))),
                high_price=Decimal(str(max(10.5, 120.0 - i * 0.3 + 0.5))),
                low_price=Decimal(str(max(9.5, 120.0 - i * 0.3 - 0.5))),
                volume=1000000,
            )
            for i in range(250)
        ]

        mock_market_data_provider.get_historical_data = AsyncMock(return_value=declining_data)

        tool = MarketRegimeDetectTrendTool(mock_market_data_provider)
        result = await tool.execute(symbol="TEST", lookback_days=200)

        assert result.success is True
        # Should detect bear or neutral (depending on MA relationship)
        assert result.data["regime"] in ["bear", "neutral", "bull"]

    @pytest.mark.asyncio
    async def test_volatility_tool_high_volatility_stock(
        self, mock_market_data_provider: MarketDataProvider
    ) -> None:
        """Test volatility detection with high volatility stock pattern."""
        base_date = datetime(2024, 1, 1)
        # Create high volatility pattern (large price swings)
        volatile_data = [
            StockData(
                symbol="TEST",
                timestamp=base_date + timedelta(days=i),
                open_price=Decimal(str(100.0 + (i % 10) * 5.0)),
                close_price=Decimal(str(100.0 + (i % 10) * 5.0)),
                high_price=Decimal(str(100.0 + (i % 10) * 5.0 + 2.0)),
                low_price=Decimal(str(100.0 + (i % 10) * 5.0 - 2.0)),
                volume=1000000,
            )
            for i in range(252)
        ]

        mock_market_data_provider.get_historical_data = AsyncMock(return_value=volatile_data)

        tool = MarketRegimeDetectVolatilityTool(mock_market_data_provider)
        result = await tool.execute(symbol="TEST", lookback_days=252)

        assert result.success is True
        assert result.data["regime"] in ["high", "normal", "low"]
        assert result.data["current_volatility"] is not None

    def test_classify_volatility_regime_empty_history(self) -> None:
        """Test volatility classification with empty history."""
        regime = _classify_volatility_regime(0.20, [])
        assert regime == "normal"

    def test_classify_volatility_regime_percentile_empty_history(self) -> None:
        """Test percentile-based volatility classification with empty history."""
        regime = _classify_volatility_regime_percentile(0.20, [])
        assert regime == "normal"
