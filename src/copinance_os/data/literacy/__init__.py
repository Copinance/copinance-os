"""Feature-keyed, literacy-tiered narrative strings for deterministic analytics.

Each module here pairs with an engine elsewhere (for example ``options_positioning`` with
``data.analytics.options.positioning``). Shared primitives live in ``copinance_os.domain.literacy``.
"""

from __future__ import annotations

from . import instrument_analysis, macro_indicators, market_regime, options_positioning

__all__ = ["instrument_analysis", "macro_indicators", "market_regime", "options_positioning"]
