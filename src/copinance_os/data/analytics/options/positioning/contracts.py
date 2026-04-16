"""Option-contract field accessors (strikes, OI, quotes, expirations)."""

from __future__ import annotations

from datetime import date, datetime

from copinance_os.data.analytics.options.positioning.math import safe_float
from copinance_os.domain.models.market import OptionContract


def numeric_greek(contract: OptionContract, name: str) -> float | None:
    """Return a float from the contract or nested ``greeks``."""
    v = getattr(contract, name, None)
    if v is not None:
        try:
            return float(v)
        except (TypeError, ValueError):
            pass
    g = contract.greeks
    if g is None:
        return None
    v2 = getattr(g, name, None)
    if v2 is None:
        return None
    try:
        return float(v2)
    except (TypeError, ValueError):
        return None


def contract_strike(c: OptionContract) -> float:
    return safe_float(c.strike)


def contract_expiration_iso(c: OptionContract) -> str:
    return c.expiration_date.isoformat()


def contract_oi(c: OptionContract) -> int | None:
    v = c.open_interest
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def contract_vol(c: OptionContract) -> int | None:
    v = c.volume
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def contract_iv_pct(c: OptionContract) -> float | None:
    raw = c.implied_volatility
    if raw is None:
        return None
    iv = safe_float(raw)
    if iv <= 0:
        return None
    if iv < 2.0:
        iv *= 100.0
    return iv


def contract_bid_ask(c: OptionContract) -> tuple[float, float]:
    bid = safe_float(c.bid)
    ask = safe_float(c.ask)
    return bid, ask


def contract_mid_price(c: OptionContract) -> float:
    bid, ask = contract_bid_ask(c)
    if bid > 0 or ask > 0:
        mid = (bid + ask) / 2.0 if ask >= bid else max(bid, ask)
        if mid > 0:
            return mid
    last = safe_float(getattr(c, "last_price", None))
    return last if last > 0 else 0.0


def parse_expiration_to_date(exp: str) -> date | None:
    exp = exp.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(exp, fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(exp)
    except ValueError:
        return None


def expiration_sort_key(s: str) -> tuple[int, str]:
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(s, fmt).date()
            return (0, dt.isoformat())
        except ValueError:
            continue
    return (1, s)


def sorted_expirations(calls: list[OptionContract], puts: list[OptionContract]) -> list[str]:
    """Return unique expiration ISO strings that appear on at least one leg.

    Provider metadata can list expirations without option rows for that strip;
    nearest-expiry selection follows contract rows only.
    """
    out = {contract_expiration_iso(c) for c in (*calls, *puts)}
    return sorted(out, key=expiration_sort_key)


def nearest_expirations(sorted_exp: list[str], n: int = 2) -> list[str]:
    if not sorted_exp:
        return []
    ordered = sorted(sorted_exp, key=expiration_sort_key)
    return ordered[:n]


def atm_strike(strikes: list[float], underlying: float) -> float | None:
    if not strikes or underlying <= 0:
        return None
    return min(strikes, key=lambda s: abs(s - underlying))


def contracts_for_expiration(contracts: list[OptionContract], exp: str) -> list[OptionContract]:
    return [c for c in contracts if contract_expiration_iso(c) == exp]
