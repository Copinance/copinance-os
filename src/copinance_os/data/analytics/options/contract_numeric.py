"""Read numeric fields from normalized ``OptionContract`` (Greeks + quote fields)."""

from __future__ import annotations

from copinance_os.domain.models.market import OptionContract


def contract_numeric(contract: OptionContract, name: str) -> float:
    """Return a float from the contract or nested ``greeks`` (matches Copinance backend)."""
    v = getattr(contract, name, None)
    if v is not None:
        try:
            return float(v)
        except (TypeError, ValueError):
            pass
    g = contract.greeks
    if g is None:
        return 0.0
    v2 = getattr(g, name, None)
    if v2 is None:
        return 0.0
    try:
        return float(v2)
    except (TypeError, ValueError):
        return 0.0
