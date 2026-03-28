"""Unit tests for stock symbol validator."""

import pytest

from copinance_os.domain.validation.stock_symbol_validator import StockSymbolValidator


@pytest.mark.unit
class TestStockSymbolValidator:
    """Test StockSymbolValidator."""

    def test_is_valid_symbol_format_valid_symbols(self) -> None:
        """Test is_valid_symbol_format with valid symbols."""
        assert StockSymbolValidator.is_valid_symbol_format("AAPL") is True
        assert StockSymbolValidator.is_valid_symbol_format("MSFT") is True
        assert StockSymbolValidator.is_valid_symbol_format("GOOGL") is True
        assert StockSymbolValidator.is_valid_symbol_format("A") is True
        assert StockSymbolValidator.is_valid_symbol_format("BRK.B") is False  # Contains dot
        assert (
            StockSymbolValidator.is_valid_symbol_format("12345") is False
        )  # Purely numeric (no letters, isupper() returns False)

    def test_is_valid_symbol_format_invalid_symbols(self) -> None:
        """Test is_valid_symbol_format with invalid symbols."""
        assert StockSymbolValidator.is_valid_symbol_format("") is False
        assert StockSymbolValidator.is_valid_symbol_format("aapl") is False  # Lowercase
        assert StockSymbolValidator.is_valid_symbol_format("AAPL ") is False  # Trailing space
        assert StockSymbolValidator.is_valid_symbol_format(" AAPL") is False  # Leading space
        assert StockSymbolValidator.is_valid_symbol_format("AAPL-") is False  # Special char
        assert StockSymbolValidator.is_valid_symbol_format("TOOLONG") is False  # Too long
        assert StockSymbolValidator.is_valid_symbol_format("A B") is False  # Contains space

    def test_looks_like_symbol_valid_symbols(self) -> None:
        """Test looks_like_symbol with valid symbols."""
        assert StockSymbolValidator.looks_like_symbol("AAPL") is True
        assert StockSymbolValidator.looks_like_symbol("MSFT") is True
        assert StockSymbolValidator.looks_like_symbol("GOOGL") is True
        assert StockSymbolValidator.looks_like_symbol("A") is True

    def test_looks_like_symbol_invalid_symbols(self) -> None:
        """Test looks_like_symbol with invalid symbols."""
        assert StockSymbolValidator.looks_like_symbol("aapl") is False  # Lowercase
        assert StockSymbolValidator.looks_like_symbol("Apple") is False  # Mixed case
        assert StockSymbolValidator.looks_like_symbol("") is False
        assert StockSymbolValidator.looks_like_symbol("AAPL ") is False  # Trailing space
        assert StockSymbolValidator.looks_like_symbol("TOOLONG") is False  # Too long
        assert StockSymbolValidator.looks_like_symbol("Apple Inc") is False  # Company name

    def test_looks_like_symbol_vs_is_valid_format(self) -> None:
        """Test that looks_like_symbol and is_valid_symbol_format behave similarly for uppercase."""
        # For uppercase valid symbols, both should return True
        assert StockSymbolValidator.looks_like_symbol(
            "AAPL"
        ) == StockSymbolValidator.is_valid_symbol_format("AAPL")
        assert StockSymbolValidator.looks_like_symbol(
            "MSFT"
        ) == StockSymbolValidator.is_valid_symbol_format("MSFT")

        # For lowercase, looks_like_symbol should be False, is_valid_symbol_format should be False
        assert StockSymbolValidator.looks_like_symbol("aapl") is False
        assert StockSymbolValidator.is_valid_symbol_format("aapl") is False
