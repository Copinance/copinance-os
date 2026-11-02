"""Gate specific vendor fetches a host's own data layer already owns.

This is a narrower, opt-in control than the engine/standalone split in
``infra.di.data_providers``: that switch decides whether vendor adapters (YFinance,
FRED, ...) exist at all, while this gate lets a standalone deployment keep most
vendor fetches but refuse the few datasets ("covered fetches") that a sibling
service has taken over fetching, so copinance-os never becomes a second writer
for them. When ``COPINANCE_USE_MARKET_FACTS=1``, calls for a covered dataset raise
instead of hitting the vendor.

Only datasets with an actual ``refuse_covered_fetch`` call site belong in
``MARKET_COVERED_FETCHES`` — see ``YFinanceMarketProvider`` for the current ones.
"""

from __future__ import annotations

import os

# Datasets gated at their vendor call site (see YFinanceMarketProvider).
MARKET_COVERED_FETCHES: frozenset[str] = frozenset(
    {
        "quote",
        "historical",
        "option_chain",
    }
)


class MarketFactFetchRetiredError(RuntimeError):
    """Raised when OS must not call a provider for a Market-owned observation."""

    def __init__(self, dataset: str) -> None:
        self.dataset = dataset
        super().__init__(
            f"Market owns {dataset} observations; set COPINANCE_USE_MARKET_FACTS=0"
            " only for local provider experiments, never as a second writer."
        )


MarketFactFetchRetired = MarketFactFetchRetiredError


def use_market_facts() -> bool:
    return os.environ.get("COPINANCE_USE_MARKET_FACTS", "").strip() in {"1", "true", "TRUE", "yes"}


def refuse_covered_fetch(dataset: str) -> None:
    if use_market_facts() and dataset in MARKET_COVERED_FETCHES:
        raise MarketFactFetchRetiredError(dataset)
