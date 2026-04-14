"""BSM Greek estimation defaults and profile-driven assumption resolution."""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from copinance_os.domain.models.profile import AnalysisProfile
from copinance_os.infra.config import Settings

DEFAULT_RISK_FREE_RATE: Final[Decimal] = Decimal("0.045")

PROFILE_PREF_OPTION_GREEKS_RISK_FREE_RATE = "option_greeks_risk_free_rate"
PROFILE_PREF_OPTION_GREEKS_DIVIDEND_YIELD_DEFAULT = "option_greeks_dividend_yield_default"


def resolve_option_greek_assumptions(
    *,
    settings: Settings,
    profile: AnalysisProfile | None = None,
) -> tuple[Decimal, Decimal]:
    """Return ``(risk_free_rate, dividend_yield_default)`` for BSM Greek estimation.

    Precedence for each value: ``AnalysisProfile.preferences`` (if ``profile`` is given),
    then :class:`Settings`, then built-in defaults.

    ``dividend_yield_default`` is used only when the options chain metadata has no
    ``dividend_yield`` entry.
    """
    rf_pref = (
        profile.preferences.get(PROFILE_PREF_OPTION_GREEKS_RISK_FREE_RATE)
        if profile is not None
        else None
    )
    div_pref = (
        profile.preferences.get(PROFILE_PREF_OPTION_GREEKS_DIVIDEND_YIELD_DEFAULT)
        if profile is not None
        else None
    )

    if rf_pref is not None and str(rf_pref).strip():
        risk_free = Decimal(str(rf_pref))
    elif settings.option_greeks_risk_free_rate is not None:
        risk_free = Decimal(str(settings.option_greeks_risk_free_rate))
    else:
        risk_free = DEFAULT_RISK_FREE_RATE

    if div_pref is not None and str(div_pref).strip():
        div_default = Decimal(str(div_pref))
    elif settings.option_greeks_dividend_yield_default is not None:
        div_default = Decimal(str(settings.option_greeks_dividend_yield_default))
    else:
        div_default = Decimal("0")

    return risk_free, div_default
