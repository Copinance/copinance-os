"""Market-owned fetch gate for OS providers."""

import pytest

from copinance_os.data.providers.market_facts import (
    MarketFactFetchRetired,
    refuse_covered_fetch,
    use_market_facts,
)


def test_gate_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COPINANCE_USE_MARKET_FACTS", raising=False)
    assert use_market_facts() is False
    refuse_covered_fetch("quote")  # no raise


def test_gate_refuses_covered_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COPINANCE_USE_MARKET_FACTS", "1")
    with pytest.raises(MarketFactFetchRetired, match="quote"):
        refuse_covered_fetch("quote")
