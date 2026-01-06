"""Unit tests for Research domain model."""

import pytest

from copinanceos.domain.models.research import Research, ResearchStatus, ResearchTimeframe
from copinanceos.domain.models.research_profile import FinancialLiteracy, ResearchProfile


@pytest.mark.unit
class TestResearchModel:
    """Test Research domain model."""

    def test_create_research(self) -> None:
        """Test creating a research."""
        research = Research(
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
        )

        assert research.stock_symbol == "AAPL"
        assert research.timeframe == ResearchTimeframe.MID_TERM
        assert research.workflow_type == "stock"
        assert research.status == ResearchStatus.PENDING
        assert research.profile_id is None

    def test_research_with_profile(self) -> None:
        """Test creating research with a profile."""
        profile = ResearchProfile(financial_literacy=FinancialLiteracy.ADVANCED)
        research = Research(
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="stock",
            profile_id=profile.id,
        )

        assert research.profile_id == profile.id

    def test_research_status_transition(self) -> None:
        """Test research status can be updated."""
        research = Research(
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.SHORT_TERM,
            workflow_type="stock",
        )

        assert research.status == ResearchStatus.PENDING

        research.status = ResearchStatus.IN_PROGRESS
        assert research.status == ResearchStatus.IN_PROGRESS

        research.status = ResearchStatus.COMPLETED
        assert research.status == ResearchStatus.COMPLETED
