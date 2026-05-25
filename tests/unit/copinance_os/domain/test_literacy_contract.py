"""Tests for question-driven literacy output contracts."""

import pytest

from copinance_os.domain.literacy import literacy_output_contract_for_question_driven
from copinance_os.domain.models.entities.profile import FinancialLiteracy


@pytest.mark.unit
@pytest.mark.parametrize(
    ("tier", "needle"),
    [
        (FinancialLiteracy.BEGINNER, "MANDATORY FOR THIS USER (beginner)"),
        (FinancialLiteracy.INTERMEDIATE, "MANDATORY FOR THIS USER (intermediate)"),
        (FinancialLiteracy.ADVANCED, "MANDATORY FOR THIS USER (advanced)"),
    ],
)
def test_literacy_output_contract_labels_tier(tier: FinancialLiteracy, needle: str) -> None:
    assert needle in literacy_output_contract_for_question_driven(tier)
