"""Unit tests for market regime detection registry functions."""

from unittest.mock import MagicMock

import pytest

from copinanceos.domain.ports.data_providers import MarketDataProvider
from copinanceos.infrastructure.tools.analysis.market_regime.registry import (
    create_all_regime_tools,
    create_regime_tools_by_type,
)
from copinanceos.infrastructure.tools.analysis.market_regime.rule_based import (
    MarketRegimeDetectCyclesTool,
    MarketRegimeDetectTrendTool,
    MarketRegimeDetectVolatilityTool,
)


@pytest.fixture
def mock_market_data_provider() -> MarketDataProvider:
    """Create a mock market data provider."""
    provider = MagicMock(spec=MarketDataProvider)
    provider.get_provider_name = MagicMock(return_value="test_provider")
    return provider


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
