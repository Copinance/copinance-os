"""Unit tests for Job domain model."""

import pytest

from copinanceos.domain.models.job import Job, JobScope, JobStatus, JobTimeframe
from copinanceos.domain.models.research_profile import FinancialLiteracy, ResearchProfile


@pytest.mark.unit
class TestJobModel:
    """Test Job domain model."""

    def test_create_job(self) -> None:
        """Test creating a job."""
        job = Job(
            scope=JobScope.STOCK,
            stock_symbol="AAPL",
            timeframe=JobTimeframe.MID_TERM,
            workflow_type="stock",
        )

        assert job.stock_symbol == "AAPL"
        assert job.timeframe == JobTimeframe.MID_TERM
        assert job.workflow_type == "stock"
        assert job.status == JobStatus.PENDING
        assert job.profile_id is None

    def test_job_with_profile(self) -> None:
        """Test creating job with a profile."""
        profile = ResearchProfile(financial_literacy=FinancialLiteracy.ADVANCED)
        job = Job(
            scope=JobScope.STOCK,
            stock_symbol="AAPL",
            timeframe=JobTimeframe.MID_TERM,
            workflow_type="stock",
            profile_id=profile.id,
        )

        assert job.profile_id == profile.id

    def test_job_status_transition(self) -> None:
        """Test job status can be updated."""
        job = Job(
            scope=JobScope.STOCK,
            stock_symbol="AAPL",
            timeframe=JobTimeframe.SHORT_TERM,
            workflow_type="stock",
        )

        assert job.status == JobStatus.PENDING

        job.status = JobStatus.IN_PROGRESS
        assert job.status == JobStatus.IN_PROGRESS

        job.status = JobStatus.COMPLETED
        assert job.status == JobStatus.COMPLETED
