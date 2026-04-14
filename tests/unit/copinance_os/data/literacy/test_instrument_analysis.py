import pytest

from copinance_os.data.literacy import instrument_analysis as ia_lit
from copinance_os.domain.models.profile import FinancialLiteracy


@pytest.mark.unit
def test_instrument_assessment_tiers_differ() -> None:
    beginner = ia_lit.assessment_upper_range(FinancialLiteracy.BEGINNER)
    advanced = ia_lit.assessment_upper_range(FinancialLiteracy.ADVANCED)
    assert beginner != advanced


@pytest.mark.unit
def test_options_header_includes_symbol() -> None:
    header = ia_lit.options_header("NVDA", FinancialLiteracy.INTERMEDIATE)
    assert "NVDA" in header
