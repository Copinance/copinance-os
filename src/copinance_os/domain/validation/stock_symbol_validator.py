"""Stock symbol validation."""

import re


class StockSymbolValidator:
    """Domain validator for stock symbol validation."""

    @staticmethod
    def is_valid_symbol_format(symbol: str) -> bool:
        """Check if a string looks like a valid stock symbol.

        Stock symbols are typically 1-5 uppercase alphanumeric characters.

        Args:
            symbol: String to validate

        Returns:
            True if the string appears to be a valid stock symbol format
        """
        if not symbol or not symbol.isupper():
            return False
        # Must be 1-5 alphanumeric characters, no spaces or special chars
        return bool(re.match(r"^[A-Z0-9]{1,5}$", symbol))

    @staticmethod
    def looks_like_symbol(query: str) -> bool:
        """Check if a query looks like a stock symbol (for auto-detection).

        This is more lenient than is_valid_symbol_format - it checks if
        the query appears to be a symbol based on format and case.

        Args:
            query: Search query to check

        Returns:
            True if query appears to be a stock symbol
        """
        # Only treat as symbol if query is already uppercase (user likely typed a symbol)
        # Lowercase queries are likely company name searches
        if not query.isupper():
            return False
        # Must be 1-5 alphanumeric characters, no spaces or special chars
        return bool(re.match(r"^[A-Z0-9]{1,5}$", query))
