"""Unit tests for CLI error handling utilities."""

from unittest.mock import MagicMock, patch

import pytest

from copinanceos.application.exceptions import ApplicationError
from copinanceos.cli.error_handler import (
    _handle_application_error,
    _handle_domain_error,
    _handle_unexpected_error,
    handle_cli_error,
)
from copinanceos.domain.exceptions import DomainError


class SampleDomainError(DomainError):
    """Sample domain exception for testing."""

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class SampleApplicationError(ApplicationError):
    """Sample application exception for testing."""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message, cause)
        self.message = message
        self.cause = cause


@pytest.mark.unit
class TestErrorHandler:
    """Test CLI error handling functions."""

    @patch("copinanceos.cli.error_handler.console")
    def test_handle_domain_error(self, mock_console: MagicMock) -> None:
        """Test handling domain exceptions."""
        error = SampleDomainError("Invalid symbol", details={"symbol": "INVALID"})
        context = {"command": "get_quote"}

        _handle_domain_error(error, context)

        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        assert call_args.title == "Domain Error"
        assert call_args.border_style == "red"

    @patch("copinanceos.cli.error_handler.console")
    def test_handle_application_error(self, mock_console: MagicMock) -> None:
        """Test handling application exceptions."""
        cause = ValueError("Underlying error")
        error = SampleApplicationError("Application error occurred", cause=cause)
        context = {"command": "create_research"}

        _handle_application_error(error, context)

        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        assert call_args.title == "Application Error"
        assert call_args.border_style == "yellow"

    @patch("copinanceos.cli.error_handler.console")
    def test_handle_unexpected_error(self, mock_console: MagicMock) -> None:
        """Test handling unexpected errors."""
        error = RuntimeError("Unexpected runtime error")
        context = {"command": "unknown"}

        _handle_unexpected_error(error, context)

        mock_console.print.assert_called_once()
        call_args = mock_console.print.call_args[0][0]
        assert call_args.title == "Unexpected Error"
        assert call_args.border_style == "red"

    @patch("copinanceos.cli.error_handler._handle_domain_error")
    def test_handle_cli_error_domain_exception(self, mock_handle_domain: MagicMock) -> None:
        """Test handle_cli_error with domain exception."""
        error = SampleDomainError("Domain error")
        context = {"symbol": "AAPL"}

        handle_cli_error(error, context)

        mock_handle_domain.assert_called_once_with(error, context)

    @patch("copinanceos.cli.error_handler._handle_application_error")
    def test_handle_cli_error_application_exception(self, mock_handle_app: MagicMock) -> None:
        """Test handle_cli_error with application exception."""
        error = SampleApplicationError("Application error")
        context = {"command": "test"}

        handle_cli_error(error, context)

        mock_handle_app.assert_called_once_with(error, context)

    @patch("copinanceos.cli.error_handler._handle_unexpected_error")
    def test_handle_cli_error_unexpected_exception(self, mock_handle_unexpected: MagicMock) -> None:
        """Test handle_cli_error with unexpected exception."""
        error = ValueError("Unexpected error")
        context = None

        handle_cli_error(error, context)

        mock_handle_unexpected.assert_called_once_with(error, {})

    @patch("copinanceos.cli.error_handler._handle_unexpected_error")
    def test_handle_cli_error_without_context(self, mock_handle_unexpected: MagicMock) -> None:
        """Test handle_cli_error without context."""
        error = RuntimeError("Error without context")

        handle_cli_error(error, None)

        mock_handle_unexpected.assert_called_once_with(error, {})
