"""Shared number and value formatting for CLI display."""

from __future__ import annotations

from typing import Any

# Common Yahoo Finance exchange codes → display name (market where equity is traded)
EXCHANGE_DISPLAY_NAMES: dict[str, str] = {
    "NMS": "NASDAQ",
    "NGM": "NASDAQ",
    "NCM": "NASDAQ",
    "NYQ": "NYSE",
    "NYC": "NYSE",
    "ASE": "NYSE American",
    "BTS": "BATS",
    "PCX": "NYSE Arca",
    "BSE": "BSE",
    "NSE": "NSE",
    "LON": "LSE",
    "HKG": "HKEX",
    "TO": "TSX",
    "EPA": "Euronext Paris",
    "FRA": "XETRA",
    "ETR": "XETRA",
}


def format_exchange(exchange: str | None) -> str:
    """Return human-readable market name for an exchange code (e.g. NMS → NASDAQ)."""
    if not exchange or not str(exchange).strip():
        return ""
    code = str(exchange).strip().upper()
    return EXCHANGE_DISPLAY_NAMES.get(code, code)


def _to_float(value: Any) -> float | None:
    """Convert value to float if possible."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def format_price(value: Any) -> str:
    """Format a price for display (e.g. OHLC). Uses 2 decimal places."""
    n = _to_float(value)
    if n is None:
        return "—"
    return f"{n:,.2f}"


def format_volume(value: Any) -> str:
    """Format volume for display with K/M/B suffix (e.g. 87.5M, 1.2B)."""
    n = _to_float(value)
    if n is None:
        return "—"
    if n >= 1e9:
        return f"{n / 1e9:.1f}B"
    if n >= 1e6:
        return f"{n / 1e6:.1f}M"
    if n >= 1e3:
        return f"{n / 1e3:.1f}K"
    return f"{n:,.0f}"


def format_compact_number(value: Any, decimals: int = 2) -> str:
    """Format large numbers with T/B/M suffix for readability (e.g. 3.68T, 416.16B)."""
    n = _to_float(value)
    if n is None:
        return "N/A"
    if abs(n) >= 1e12:
        return f"{n / 1e12:.{decimals}f}T"
    if abs(n) >= 1e9:
        return f"{n / 1e9:.{decimals}f}B"
    if abs(n) >= 1e6:
        return f"{n / 1e6:.{decimals}f}M"
    if abs(n) >= 1e3:
        return f"{n / 1e3:.{decimals}f}K"
    if isinstance(value, float) or (isinstance(value, (int, float)) and abs(n) != int(n)):
        return f"{n:.{decimals}f}"
    return f"{int(n):,}"
