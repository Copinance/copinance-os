import pytest

from copinance_os.data.literacy import market_regime as mr_lit
from copinance_os.domain.models.profile import FinancialLiteracy


@pytest.mark.unit
def test_vix_sentiment_varies_by_tier() -> None:
    assert mr_lit.vix_sentiment_label(
        "panic", FinancialLiteracy.BEGINNER
    ) != mr_lit.vix_sentiment_label("panic", FinancialLiteracy.ADVANCED)


@pytest.mark.unit
def test_cycle_description_exists() -> None:
    desc = mr_lit.cycle_phase_description("distribution", FinancialLiteracy.INTERMEDIATE)
    assert desc
