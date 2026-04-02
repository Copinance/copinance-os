"""Unit tests for cache CLI commands."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copinance_os.interfaces.cli.commands.cache import cache_info, clear_cache, refresh_cache


@pytest.mark.unit
class TestCacheCLI:
    """Test cache-related CLI commands."""

    @patch("copinance_os.interfaces.cli.commands.cache.get_container")
    @patch("copinance_os.interfaces.cli.commands.cache.Console")
    def test_clear_cache_all(
        self, mock_console_class: MagicMock, mock_get_container: MagicMock
    ) -> None:
        """Test clear cache command without tool name."""
        mock_console = mock_console_class.return_value
        mock_cache_manager = AsyncMock()
        mock_cache_manager.clear = AsyncMock(return_value=5)
        mock_get_container.return_value.cache_manager.return_value = mock_cache_manager

        clear_cache(tool_name=None)

        mock_get_container.return_value.cache_manager.assert_called_once()
        mock_cache_manager.clear.assert_called_once_with(None)
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        assert "Cleared 5" in call_args and "cache" in call_args.lower()

    @patch("copinance_os.interfaces.cli.commands.cache.get_container")
    @patch("copinance_os.interfaces.cli.commands.cache.Console")
    def test_clear_cache_specific_tool(
        self, mock_console_class: MagicMock, mock_get_container: MagicMock
    ) -> None:
        """Test clear cache command with specific tool name."""
        mock_console = mock_console_class.return_value
        mock_cache_manager = AsyncMock()
        mock_cache_manager.clear = AsyncMock(return_value=3)
        mock_get_container.return_value.cache_manager.return_value = mock_cache_manager

        clear_cache(tool_name="get_market_quote")

        mock_get_container.return_value.cache_manager.assert_called_once()
        mock_cache_manager.clear.assert_called_once_with("get_market_quote")
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        assert "Cleared 3 cache entries for tool: get_market_quote" in call_args

    @patch("copinance_os.interfaces.cli.commands.cache.get_container")
    @patch("copinance_os.interfaces.cli.commands.cache.Console")
    def test_refresh_cache_with_args(
        self, mock_console_class: MagicMock, mock_get_container: MagicMock
    ) -> None:
        """Test refresh cache command with cache key args."""
        mock_console = mock_console_class.return_value
        mock_cache_manager = AsyncMock()
        mock_cache_manager.delete = AsyncMock(return_value=True)
        mock_get_container.return_value.cache_manager.return_value = mock_cache_manager

        refresh_cache(tool_name="get_market_quote", args=["symbol=AAPL"])

        mock_get_container.return_value.cache_manager.assert_called_once()
        mock_cache_manager.delete.assert_called_once_with("get_market_quote", symbol="AAPL")
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        assert "Refreshed cache for get_market_quote" in call_args
        assert "symbol=AAPL" in call_args

    @patch("copinance_os.interfaces.cli.commands.cache.get_container")
    @patch("copinance_os.interfaces.cli.commands.cache.Console")
    def test_refresh_cache_without_args(
        self, mock_console_class: MagicMock, mock_get_container: MagicMock
    ) -> None:
        """Test refresh cache command without args."""
        mock_console = mock_console_class.return_value
        mock_cache_manager = AsyncMock()
        mock_cache_manager.delete = AsyncMock(return_value=True)
        mock_get_container.return_value.cache_manager.return_value = mock_cache_manager

        refresh_cache(tool_name="get_market_quote", args=[])

        mock_get_container.return_value.cache_manager.assert_called_once()
        mock_cache_manager.delete.assert_called_once_with("get_market_quote")
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        assert "Refreshed cache for get_market_quote" in call_args

    @patch("copinance_os.interfaces.cli.commands.cache.get_container")
    @patch("copinance_os.interfaces.cli.commands.cache.Console")
    def test_refresh_cache_not_found(
        self, mock_console_class: MagicMock, mock_get_container: MagicMock
    ) -> None:
        """Test refresh cache command when entry not found."""
        mock_console = mock_console_class.return_value
        mock_cache_manager = AsyncMock()
        mock_cache_manager.delete = AsyncMock(return_value=False)
        mock_get_container.return_value.cache_manager.return_value = mock_cache_manager

        refresh_cache(tool_name="get_market_quote", args=["symbol=AAPL"])

        mock_get_container.return_value.cache_manager.assert_called_once()
        mock_cache_manager.delete.assert_called_once_with("get_market_quote", symbol="AAPL")
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        assert "No cache entry found for get_market_quote" in call_args

    @patch("copinance_os.interfaces.cli.commands.cache.get_container")
    @patch("copinance_os.interfaces.cli.commands.cache.Console")
    def test_cache_info(self, mock_console_class: MagicMock, mock_get_container: MagicMock) -> None:
        """Test cache info command."""
        mock_console = mock_console_class.return_value
        mock_cache_manager = MagicMock()
        mock_backend = MagicMock()
        mock_backend.get_backend_name.return_value = "local_file"
        mock_backend._cache_dir = "/path/to/cache"
        mock_cache_manager.get_backend.return_value = mock_backend
        mock_get_container.return_value.cache_manager.return_value = mock_cache_manager

        cache_info()

        mock_get_container.return_value.cache_manager.assert_called_once()
        mock_cache_manager.get_backend.assert_called_once()
        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        assert hasattr(call_args, "title")  # It's a Table object
