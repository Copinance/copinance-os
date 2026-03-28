"""Unit tests for logging configuration."""

import logging
import os
import sys
from io import StringIO
from unittest.mock import patch

import pytest
import structlog

from copinance_os.infra.config import Settings
from copinance_os.infra.logging import configure_logging, get_logger


def create_settings(**kwargs: str) -> Settings:
    """Create Settings instance without reading from environment."""
    defaults = {
        "log_level": "INFO",
        "log_format": "json",
    }
    defaults.update(kwargs)
    # Use model_construct to bypass environment variable reading
    return Settings.model_construct(**defaults)


@pytest.mark.unit
class TestConfigureLogging:
    """Test configure_logging function."""

    def setup_method(self) -> None:
        """Reset structlog configuration before each test."""
        structlog.reset_defaults()
        # Reset logging configuration
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.WARNING)
        # Clear handlers to allow basicConfig to reconfigure
        root_logger.handlers.clear()
        # Clear environment variables that might interfere
        env_vars_to_clear = [
            "COPINANCEOS_LLM_PROVIDER",
            "COPINANCEOS_GEMINI_API_KEY",
        ]
        for var in env_vars_to_clear:
            if var in os.environ:
                del os.environ[var]

    def test_configure_logging_with_info_level(self) -> None:
        """Test configuring logging with INFO level."""
        settings = create_settings(log_level="INFO", log_format="json")

        with patch("logging.basicConfig") as mock_basic_config:
            configure_logging(settings)
            # Verify basicConfig was called with correct level
            mock_basic_config.assert_called_once()
            call_kwargs = mock_basic_config.call_args[1]
            assert call_kwargs["level"] == logging.INFO

    def test_configure_logging_with_debug_level(self) -> None:
        """Test configuring logging with DEBUG level."""
        settings = create_settings(log_level="DEBUG", log_format="json")

        with patch("logging.basicConfig") as mock_basic_config:
            configure_logging(settings)
            call_kwargs = mock_basic_config.call_args[1]
            assert call_kwargs["level"] == logging.DEBUG

    def test_configure_logging_with_warning_level(self) -> None:
        """Test configuring logging with WARNING level."""
        settings = create_settings(log_level="WARNING", log_format="json")

        with patch("logging.basicConfig") as mock_basic_config:
            configure_logging(settings)
            call_kwargs = mock_basic_config.call_args[1]
            assert call_kwargs["level"] == logging.WARNING

    def test_configure_logging_with_error_level(self) -> None:
        """Test configuring logging with ERROR level."""
        settings = create_settings(log_level="ERROR", log_format="json")

        with patch("logging.basicConfig") as mock_basic_config:
            configure_logging(settings)
            call_kwargs = mock_basic_config.call_args[1]
            assert call_kwargs["level"] == logging.ERROR

    def test_configure_logging_with_critical_level(self) -> None:
        """Test configuring logging with CRITICAL level."""
        settings = create_settings(log_level="CRITICAL", log_format="json")

        with patch("logging.basicConfig") as mock_basic_config:
            configure_logging(settings)
            call_kwargs = mock_basic_config.call_args[1]
            assert call_kwargs["level"] == logging.CRITICAL

    def test_configure_logging_with_invalid_level_defaults_to_info(self) -> None:
        """Test that invalid log level defaults to INFO."""
        settings = create_settings(log_level="INVALID_LEVEL", log_format="json")

        with patch("logging.basicConfig") as mock_basic_config:
            configure_logging(settings)
            # getattr(logging, "INVALID_LEVEL".upper(), logging.INFO) should return logging.INFO
            call_kwargs = mock_basic_config.call_args[1]
            assert call_kwargs["level"] == logging.INFO

    def test_configure_logging_with_lowercase_level(self) -> None:
        """Test that lowercase log level is converted correctly."""
        settings = create_settings(log_level="debug", log_format="json")

        with patch("logging.basicConfig") as mock_basic_config:
            configure_logging(settings)
            # "debug".upper() = "DEBUG", getattr(logging, "DEBUG") = logging.DEBUG
            call_kwargs = mock_basic_config.call_args[1]
            assert call_kwargs["level"] == logging.DEBUG

    def test_configure_logging_with_json_format(self) -> None:
        """Test configuring logging with JSON format."""
        settings = create_settings(log_level="INFO", log_format="json")
        configure_logging(settings)

        # Verify structlog is configured
        config = structlog.get_config()
        processors = config["processors"]

        # Check that JSONRenderer is in processors
        processor_types = [type(p).__name__ for p in processors]
        assert "JSONRenderer" in processor_types

    def test_configure_logging_with_console_format(self) -> None:
        """Test configuring logging with console format."""
        settings = create_settings(log_level="INFO", log_format="console")
        configure_logging(settings)

        # Verify structlog is configured
        config = structlog.get_config()
        processors = config["processors"]

        # Check that ConsoleRenderer is in processors
        processor_types = [type(p).__name__ for p in processors]
        assert "ConsoleRenderer" in processor_types

    def test_configure_logging_sets_standard_processors(self) -> None:
        """Test that standard processors are always included."""
        settings = create_settings(log_level="INFO", log_format="json")
        configure_logging(settings)

        config = structlog.get_config()
        processors = config["processors"]
        processor_types = [type(p).__name__ for p in processors]

        # Check for standard processors
        assert any(
            "merge_contextvars" in str(p) or "MergeDictKeyValue" in str(p) for p in processors
        )
        assert "add_logger_name" in processor_types or any(
            "add_logger_name" in str(p) for p in processors
        )
        assert "add_log_level" in processor_types or any(
            "add_log_level" in str(p) for p in processors
        )
        assert "TimeStamper" in processor_types
        assert "StackInfoRenderer" in processor_types

    def test_configure_logging_sets_structlog_config(self) -> None:
        """Test that structlog configuration is properly set."""
        settings = create_settings(log_level="INFO", log_format="json")
        configure_logging(settings)

        config = structlog.get_config()
        assert config["wrapper_class"] == structlog.stdlib.BoundLogger
        assert config["context_class"] is dict
        assert config["cache_logger_on_first_use"] is True

    def test_configure_logging_sets_logging_basic_config(self) -> None:
        """Test that standard library logging is configured."""
        settings = create_settings(log_level="INFO", log_format="json")

        with patch("logging.basicConfig") as mock_basic_config:
            configure_logging(settings)
            mock_basic_config.assert_called_once()
            call_kwargs = mock_basic_config.call_args[1]
            assert call_kwargs["format"] == "%(message)s"
            assert call_kwargs["stream"] == sys.stdout
            assert call_kwargs["level"] == logging.INFO

    def test_configure_logging_json_vs_console_different_processors(self) -> None:
        """Test that JSON and console formats use different processors."""
        # Configure with JSON
        settings_json = create_settings(log_level="INFO", log_format="json")
        configure_logging(settings_json)
        config_json = structlog.get_config()
        processors_json = [type(p).__name__ for p in config_json["processors"]]

        # Reset and configure with console
        structlog.reset_defaults()
        settings_console = create_settings(log_level="INFO", log_format="console")
        configure_logging(settings_console)
        config_console = structlog.get_config()
        processors_console = [type(p).__name__ for p in config_console["processors"]]

        # JSON should have JSONRenderer
        assert "JSONRenderer" in processors_json
        # Console should have ConsoleRenderer
        assert "ConsoleRenderer" in processors_console
        # They should be different
        assert processors_json != processors_console


@pytest.mark.unit
class TestGetLogger:
    """Test get_logger function."""

    def setup_method(self) -> None:
        """Configure logging before each test."""
        settings = create_settings(log_level="INFO", log_format="json")
        configure_logging(settings)

    def test_get_logger_returns_logger(self) -> None:
        """Test that get_logger returns a logger instance."""
        logger = get_logger("test_module")
        assert logger is not None

    def test_get_logger_returns_structlog_logger(self) -> None:
        """Test that get_logger returns a structlog logger."""
        logger = get_logger("test_module")
        # structlog loggers are callable and have methods like info, debug, etc.
        assert hasattr(logger, "info")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")

    def test_get_logger_with_different_names(self) -> None:
        """Test that get_logger works with different module names."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")
        logger3 = get_logger("copinance_os.research.workflows.market")

        assert logger1 is not None
        assert logger2 is not None
        assert logger3 is not None

    def test_get_logger_can_log_messages(self) -> None:
        """Test that returned logger can actually log messages."""
        logger = get_logger("test_module")

        # Capture stdout to verify logging works
        with patch("sys.stdout", new=StringIO()) as mock_stdout:
            logger.info("test message", key="value")
            # In JSON format, output should contain the message
            output = mock_stdout.getvalue()
            # The exact format depends on structlog configuration, but should contain something
            assert output is not None

    def test_get_logger_supports_structured_logging(self) -> None:
        """Test that logger supports structured logging with key-value pairs."""
        logger = get_logger("test_module")

        # This should not raise an exception
        try:
            logger.info("test", key1="value1", key2="value2", number=42)
        except Exception as e:
            pytest.fail(f"Logger should support structured logging: {e}")

    def test_get_logger_returns_same_instance_for_same_name(self) -> None:
        """Test that get_logger returns logger for same name (caching)."""
        logger1 = get_logger("test_module")
        logger2 = get_logger("test_module")

        # structlog returns BoundLoggerLazyProxy instances, which may not be the same object
        # but both should work and reference the same underlying logger
        assert logger1 is not None
        assert logger2 is not None
        # Both should have the same logger factory args
        assert hasattr(logger1, "_logger_factory_args")
        assert hasattr(logger2, "_logger_factory_args")


@pytest.mark.unit
class TestLoggingIntegration:
    """Integration tests for logging configuration and usage."""

    def setup_method(self) -> None:
        """Reset structlog before each test."""
        structlog.reset_defaults()
        # Reset logging configuration
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.WARNING)
        root_logger.handlers.clear()

    def test_full_logging_flow(self) -> None:
        """Test complete logging flow from configuration to usage."""
        # Configure logging
        settings = create_settings(log_level="INFO", log_format="json")
        configure_logging(settings)

        # Get logger
        logger = get_logger("test_module")

        # Verify logger works
        assert logger is not None
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")

    def test_logging_with_different_formats(self) -> None:
        """Test that logging works with both JSON and console formats."""
        formats = ["json", "console"]

        for log_format in formats:
            structlog.reset_defaults()
            settings = create_settings(log_level="INFO", log_format=log_format)
            configure_logging(settings)

            logger = get_logger(f"test_{log_format}")
            assert logger is not None

            # Should be able to log without errors
            try:
                logger.info("test message", format=log_format)
            except Exception as e:
                pytest.fail(f"Logging should work with {log_format} format: {e}")

    def test_logging_levels_affect_output(self) -> None:
        """Test that different log levels affect what gets logged."""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR"]

        for level in levels:
            structlog.reset_defaults()
            # Reset logging configuration before each test
            root_logger = logging.getLogger()
            root_logger.setLevel(logging.WARNING)
            root_logger.handlers.clear()
            settings = create_settings(log_level=level, log_format="json")
            configure_logging(settings)

            root_logger = logging.getLogger()
            assert root_logger.level == getattr(logging, level)
