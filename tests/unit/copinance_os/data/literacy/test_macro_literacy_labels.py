import pytest

from copinance_os.data.literacy import macro_indicators as macro_lit
from copinance_os.domain.models.profile import FinancialLiteracy


@pytest.mark.unit
def test_macro_label_mapping_differs_for_beginner() -> None:
    beginner = macro_lit.interpret_label("very_tight", FinancialLiteracy.BEGINNER)
    advanced = macro_lit.interpret_label("very_tight", FinancialLiteracy.ADVANCED)
    assert beginner != advanced


@pytest.mark.unit
def test_macro_unknown_label_passthrough() -> None:
    assert (
        macro_lit.interpret_label("custom_value", FinancialLiteracy.INTERMEDIATE) == "custom_value"
    )
