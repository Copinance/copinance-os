"""Tests for option Greek assumption resolution (settings + profile)."""

from decimal import Decimal

import pytest

from copinance_os.data.analytics.options.greeks.config import (
    DEFAULT_RISK_FREE_RATE,
    PROFILE_PREF_OPTION_GREEKS_DIVIDEND_YIELD_DEFAULT,
    PROFILE_PREF_OPTION_GREEKS_RISK_FREE_RATE,
    resolve_option_greek_assumptions,
)
from copinance_os.domain.models.profile import AnalysisProfile, FinancialLiteracy
from copinance_os.infra.config import Settings


@pytest.mark.unit
def test_resolve_uses_settings_when_no_profile() -> None:
    settings = Settings(
        option_greeks_risk_free_rate=0.05,
        option_greeks_dividend_yield_default=0.02,
    )
    rf, div = resolve_option_greek_assumptions(settings=settings, profile=None)
    assert rf == Decimal("0.05")
    assert div == Decimal("0.02")


@pytest.mark.unit
def test_resolve_defaults_without_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("COPINANCEOS_OPTION_GREEKS_RISK_FREE_RATE", raising=False)
    monkeypatch.delenv("COPINANCEOS_OPTION_GREEKS_DIVIDEND_YIELD_DEFAULT", raising=False)
    settings = Settings()
    rf, div = resolve_option_greek_assumptions(settings=settings, profile=None)
    assert rf == DEFAULT_RISK_FREE_RATE
    assert div == Decimal("0")


@pytest.mark.unit
def test_profile_preferences_override_settings() -> None:
    settings = Settings(
        option_greeks_risk_free_rate=0.05,
        option_greeks_dividend_yield_default=0.01,
    )
    profile = AnalysisProfile(
        financial_literacy=FinancialLiteracy.ADVANCED,
        preferences={
            PROFILE_PREF_OPTION_GREEKS_RISK_FREE_RATE: "0.04",
            PROFILE_PREF_OPTION_GREEKS_DIVIDEND_YIELD_DEFAULT: "0.015",
        },
    )
    rf, div = resolve_option_greek_assumptions(settings=settings, profile=profile)
    assert rf == Decimal("0.04")
    assert div == Decimal("0.015")
