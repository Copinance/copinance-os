"""Unit tests for AnalysisProfile domain model."""

import pytest

from copinance_os.domain.models.profile import AnalysisProfile, FinancialLiteracy


@pytest.mark.unit
class TestAnalysisProfileModel:
    """Test AnalysisProfile domain model."""

    def test_create_profile(self) -> None:
        """Test creating an analysis profile."""
        profile = AnalysisProfile(
            financial_literacy=FinancialLiteracy.INTERMEDIATE,
            display_name="Test Investor",
        )

        assert profile.financial_literacy == FinancialLiteracy.INTERMEDIATE
        assert profile.display_name == "Test Investor"
        assert isinstance(profile.preferences, dict)

    def test_profile_default_literacy(self) -> None:
        """Test profile with default literacy level."""
        profile = AnalysisProfile()

        assert profile.financial_literacy == FinancialLiteracy.BEGINNER
