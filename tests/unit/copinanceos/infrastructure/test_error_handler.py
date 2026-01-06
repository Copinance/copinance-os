"""Unit tests for infrastructure error handling utilities."""

from unittest.mock import MagicMock, patch

import pytest

from copinanceos.domain.exceptions import (
    DataProviderError,
    DataProviderUnavailableError,
    StockNotFoundError,
)
from copinanceos.infrastructure.error_handler import (
    convert_to_domain_exception,
    handle_infrastructure_error,
)


@pytest.mark.unit
class TestConvertToDomainError:
    """Test convert_to_domain_exception function."""

    @patch("copinanceos.infrastructure.error_handler.logger")
    def test_convert_domain_exception_returns_as_is(self, mock_logger: MagicMock) -> None:
        """Test that DomainError is returned as-is."""
        original_error = StockNotFoundError("AAPL")
        context = {"symbol": "AAPL"}

        result = convert_to_domain_exception(original_error, "TestProvider", "get_quote", context)

        assert result == original_error
        assert isinstance(result, StockNotFoundError)
        # Should still log the error
        mock_logger.warning.assert_called_once()

    @patch("copinanceos.infrastructure.error_handler.logger")
    def test_convert_network_error_to_unavailable(self, mock_logger: MagicMock) -> None:
        """Test that network errors are converted to DataProviderUnavailableError."""
        network_error = ConnectionError("Connection timeout")
        component = "YFinanceProvider"
        operation = "get_quote"

        result = convert_to_domain_exception(network_error, component, operation)

        assert isinstance(result, DataProviderUnavailableError)
        assert result.provider_name == component
        assert "operation" in result.details
        assert result.details["operation"] == operation
        assert "error_type" in result.details
        assert result.details["error_type"] == "ConnectionError"
        mock_logger.warning.assert_called_once()

    @patch("copinanceos.infrastructure.error_handler.logger")
    def test_convert_timeout_error_to_unavailable(self, mock_logger: MagicMock) -> None:
        """Test that timeout errors are converted to DataProviderUnavailableError."""
        timeout_error = TimeoutError("Request timeout occurred")
        component = "EdgarProvider"
        operation = "get_filings"

        result = convert_to_domain_exception(timeout_error, component, operation)

        assert isinstance(result, DataProviderUnavailableError)
        assert result.provider_name == component
        mock_logger.warning.assert_called_once()

    @patch("copinanceos.infrastructure.error_handler.logger")
    def test_convert_network_unreachable_error(self, mock_logger: MagicMock) -> None:
        """Test that unreachable network errors are converted to DataProviderUnavailableError."""
        unreachable_error = OSError("Network is unreachable")
        component = "YFinanceProvider"
        operation = "get_quote"

        result = convert_to_domain_exception(unreachable_error, component, operation)

        assert isinstance(result, DataProviderUnavailableError)
        assert result.provider_name == component
        mock_logger.warning.assert_called_once()

    @patch("copinanceos.infrastructure.error_handler.logger")
    def test_convert_generic_error_to_data_provider_error(self, mock_logger: MagicMock) -> None:
        """Test that generic errors are converted to DataProviderError."""
        generic_error = ValueError("Invalid data format")
        component = "YFinanceProvider"
        operation = "get_fundamentals"

        result = convert_to_domain_exception(generic_error, component, operation)

        assert isinstance(result, DataProviderError)
        assert result.provider_name == component
        assert result.operation == operation
        assert "Invalid data format" in result.message
        assert "error_type" in result.details
        assert result.details["error_type"] == "ValueError"
        mock_logger.warning.assert_called_once()

    @patch("copinanceos.infrastructure.error_handler.logger")
    def test_convert_with_context(self, mock_logger: MagicMock) -> None:
        """Test that context is included in logging."""
        error = ValueError("Test error")
        component = "TestProvider"
        operation = "test_operation"
        context = {"symbol": "AAPL", "period": "1y"}

        result = convert_to_domain_exception(error, component, operation, context)

        assert isinstance(result, DataProviderError)
        # Verify context was passed to logger
        call_args = mock_logger.warning.call_args
        assert "symbol" in call_args[1]
        assert call_args[1]["symbol"] == "AAPL"
        assert "period" in call_args[1]
        assert call_args[1]["period"] == "1y"

    @patch("copinanceos.infrastructure.error_handler.logger")
    def test_convert_without_context(self, mock_logger: MagicMock) -> None:
        """Test conversion without context."""
        error = ValueError("Test error")
        component = "TestProvider"
        operation = "test_operation"

        result = convert_to_domain_exception(error, component, operation, context=None)

        assert isinstance(result, DataProviderError)
        # Verify basic logging fields are present
        call_args = mock_logger.warning.call_args
        assert "component" in call_args[1]
        assert "operation" in call_args[1]
        assert "error_type" in call_args[1]

    @patch("copinanceos.infrastructure.error_handler.logger")
    def test_convert_keyboard_interrupt_not_converted(self, mock_logger: MagicMock) -> None:
        """Test that KeyboardInterrupt is converted to DataProviderError (not special-cased)."""
        interrupt = KeyboardInterrupt("User cancelled")
        component = "TestProvider"
        operation = "test_operation"

        result = convert_to_domain_exception(interrupt, component, operation)

        # KeyboardInterrupt doesn't match network keywords, so it becomes DataProviderError
        assert isinstance(result, DataProviderError)
        assert not isinstance(result, DataProviderUnavailableError)

    @patch("copinanceos.infrastructure.error_handler.logger")
    def test_convert_error_with_empty_message(self, mock_logger: MagicMock) -> None:
        """Test conversion of error with empty message."""
        error = Exception("")
        component = "TestProvider"
        operation = "test_operation"

        result = convert_to_domain_exception(error, component, operation)

        assert isinstance(result, DataProviderError)
        assert result.provider_name == component
        assert result.operation == operation


@pytest.mark.unit
class TestHandleInfrastructureError:
    """Test handle_infrastructure_error function."""

    @patch("copinanceos.infrastructure.error_handler.convert_to_domain_exception")
    @patch("copinanceos.infrastructure.error_handler.logger")
    def test_handle_error_raises_when_no_default(
        self, mock_logger: MagicMock, mock_convert: MagicMock
    ) -> None:
        """Test that handle_infrastructure_error raises when default_return is None."""
        error = ValueError("Test error")
        component = "TestProvider"
        operation = "test_operation"
        converted_error = DataProviderError(component, operation, "Test error")
        mock_convert.return_value = converted_error

        with pytest.raises(DataProviderError) as exc_info:
            handle_infrastructure_error(error, component, operation)

        assert exc_info.value == converted_error
        mock_convert.assert_called_once_with(error, component, operation, None)
        mock_logger.debug.assert_not_called()

    @patch("copinanceos.infrastructure.error_handler.convert_to_domain_exception")
    @patch("copinanceos.infrastructure.error_handler.logger")
    def test_handle_error_returns_default(
        self, mock_logger: MagicMock, mock_convert: MagicMock
    ) -> None:
        """Test that handle_infrastructure_error returns default when provided."""
        error = ValueError("Test error")
        component = "TestProvider"
        operation = "test_operation"
        default_value = {"default": "data"}
        converted_error = DataProviderError(component, operation, "Test error")
        mock_convert.return_value = converted_error

        result = handle_infrastructure_error(
            error, component, operation, default_return=default_value
        )

        assert result == default_value
        mock_convert.assert_called_once_with(error, component, operation, None)
        mock_logger.debug.assert_called_once()
        call_args = mock_logger.debug.call_args[1]
        assert call_args["component"] == component
        assert call_args["operation"] == operation
        assert call_args["default_return"] == default_value

    @patch("copinanceos.infrastructure.error_handler.convert_to_domain_exception")
    @patch("copinanceos.infrastructure.error_handler.logger")
    def test_handle_error_with_context(
        self, mock_logger: MagicMock, mock_convert: MagicMock
    ) -> None:
        """Test handle_infrastructure_error with context."""
        error = ValueError("Test error")
        component = "TestProvider"
        operation = "test_operation"
        context = {"symbol": "AAPL"}
        converted_error = DataProviderError(component, operation, "Test error")
        mock_convert.return_value = converted_error

        with pytest.raises(DataProviderError):
            handle_infrastructure_error(error, component, operation, context=context)

        mock_convert.assert_called_once_with(error, component, operation, context)

    @patch("copinanceos.infrastructure.error_handler.convert_to_domain_exception")
    @patch("copinanceos.infrastructure.error_handler.logger")
    def test_handle_error_with_default_none_value(
        self, mock_logger: MagicMock, mock_convert: MagicMock
    ) -> None:
        """Test that default_return=None still raises (None is not a valid default)."""
        error = ValueError("Test error")
        component = "TestProvider"
        operation = "test_operation"
        converted_error = DataProviderError(component, operation, "Test error")
        mock_convert.return_value = converted_error

        with pytest.raises(DataProviderError):
            handle_infrastructure_error(error, component, operation, default_return=None)

        mock_logger.debug.assert_not_called()

    @patch("copinanceos.infrastructure.error_handler.convert_to_domain_exception")
    @patch("copinanceos.infrastructure.error_handler.logger")
    def test_handle_error_with_default_empty_dict(
        self, mock_logger: MagicMock, mock_convert: MagicMock
    ) -> None:
        """Test that default_return={} returns empty dict."""
        error = ValueError("Test error")
        component = "TestProvider"
        operation = "test_operation"
        converted_error = DataProviderError(component, operation, "Test error")
        mock_convert.return_value = converted_error

        result = handle_infrastructure_error(error, component, operation, default_return={})

        assert result == {}
        mock_logger.debug.assert_called_once()

    @patch("copinanceos.infrastructure.error_handler.convert_to_domain_exception")
    @patch("copinanceos.infrastructure.error_handler.logger")
    def test_handle_error_with_default_empty_list(
        self, mock_logger: MagicMock, mock_convert: MagicMock
    ) -> None:
        """Test that default_return=[] returns empty list."""
        error = ValueError("Test error")
        component = "TestProvider"
        operation = "test_operation"
        converted_error = DataProviderError(component, operation, "Test error")
        mock_convert.return_value = converted_error

        result = handle_infrastructure_error(error, component, operation, default_return=[])

        assert result == []
        mock_logger.debug.assert_called_once()
