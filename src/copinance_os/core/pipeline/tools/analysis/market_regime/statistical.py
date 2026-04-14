"""Statistical market regime detection tools.

This module provides statistical methods for regime detection using:
- Hidden Markov Models (HMM) for regime inference
- Hamilton Regime Switching Models
- Bayesian regime detection
- Other statistical inference methods

These methods infer regimes probabilistically rather than using rule-based thresholds.

Academic Foundations:
    - Hamilton, J. D. (1989). A New Approach to the Economic Analysis of Nonstationary
      Time Series and the Business Cycle. Econometrica, 57(2), 357-384.
      → Regime switching models

    - Kim, C. J., & Nelson, C. R. (1999). State-Space Models with Regime Switching:
      Classical and Gibbs-Sampling Approaches with Applications. MIT Press.
      → HMM and state-space models

    - Ang, A., & Bekaert, G. (2002). International Asset Allocation with Regime Shifts.
      Review of Financial Studies, 15(4), 1137-1187.
      → Multi-regime models
"""

import structlog

from copinance_os.domain.ports.data_providers import MarketDataProvider
from copinance_os.domain.ports.tools import Tool

logger = structlog.get_logger(__name__)


def create_statistical_regime_tools(
    market_data_provider: MarketDataProvider,
) -> list[Tool]:
    """Create all statistical market regime detection tools.

    Args:
        market_data_provider: Market data provider instance

    Returns:
        List of statistical market regime detection tools

    Note:
        Statistical regime tools are intentionally not wired yet in production.
        The deterministic rule-based tools remain the supported path until
        statistical model selection and calibration are finalized.
    """
    _ = market_data_provider
    logger.info("Statistical regime tools are intentionally disabled")
    return []
