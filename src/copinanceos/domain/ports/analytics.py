"""Ports for *derived* options analytics built on top of normalized market data.

Raw quotes and chains come from ``MarketDataProvider`` implementations. Analytics
(Greeks, future scenarios, etc.) live behind small protocols so application code depends
on abstractions, not on QuantLib or other numerical engines.
"""

from typing import Protocol

from copinanceos.domain.models.market import OptionsChain


class OptionsChainGreeksEstimator(Protocol):
    """Estimates per-contract Greeks for a chain already loaded from a data provider."""

    def estimate(self, chain: OptionsChain) -> OptionsChain:
        """Return a chain with ``OptionContract.greeks`` filled where inputs allow."""
        ...
