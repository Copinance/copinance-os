"""Advanced analysis strategy interfaces."""

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from copinanceos.domain.models.job import Job


class ScreeningStrategy(ABC):
    """Interface for company screening strategies."""

    @abstractmethod
    async def screen(
        self,
        criteria: dict[str, Any],
        universe: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Screen companies based on criteria.

        Criteria can include:
        - Quality metrics (ROE, FCF growth, Debt ratios)
        - Valuation (P/E, P/B, DCF-based)
        - Momentum (price momentum, institutional flow)
        - Sentiment (analyst ratings, social sentiment)
        - Thematic fit (ESG, industry disruption)
        """
        pass


class DueDiligenceStrategy(ABC):
    """Interface for deep due diligence analysis."""

    @abstractmethod
    async def competitive_analysis(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """
        Perform competitive analysis.

        Porter's Five Forces with real-time data.
        """
        pass

    @abstractmethod
    async def management_assessment(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """
        Assess management quality.

        Includes:
        - Track record analysis via LinkedIn
        - Executive speech sentiment
        - Insider trading pattern analysis
        """
        pass

    @abstractmethod
    async def financial_health_analysis(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """
        Analyze financial health.

        Includes:
        - Automated ratio analysis
        - Peer benchmarking
        - Bankruptcy prediction models
        """
        pass

    @abstractmethod
    async def moat_analysis(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """
        Analyze competitive moat (MoAT).

        Includes:
        - Network effects quantification
        - Brand strength via social media
        - Patent analysis using NLP
        - Switching costs assessment
        """
        pass


class ValuationStrategy(ABC):
    """Interface for valuation strategies."""

    @abstractmethod
    async def dcf_valuation(
        self,
        symbol: str,
        assumptions: dict[str, Any],
    ) -> dict[str, Any]:
        """DCF valuation with Monte Carlo simulation."""
        pass

    @abstractmethod
    async def comparable_company_analysis(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """Comparable company analysis with ML-selected peers."""
        pass

    @abstractmethod
    async def precedent_transactions(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """Precedent transactions analysis with adjustment algorithms."""
        pass

    @abstractmethod
    async def sum_of_parts_valuation(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """Sum-of-the-parts valuation for conglomerates."""
        pass

    @abstractmethod
    async def synthesize_valuation(
        self,
        symbol: str,
        methods: list[str],
    ) -> dict[str, Any]:
        """
        Synthesize multiple valuation methods.

        Uses Bayesian weighting based on method accuracy history.
        """
        pass


class RiskAssessmentStrategy(ABC):
    """Interface for comprehensive risk assessment."""

    @abstractmethod
    async def assess_business_risk(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """Assess business risk including industry disruption probability."""
        pass

    @abstractmethod
    async def assess_financial_risk(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """Assess financial risk including liquidity stress tests."""
        pass

    @abstractmethod
    async def assess_governance_risk(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """Assess governance risk including board independence and alignment."""
        pass

    @abstractmethod
    async def assess_esg_risk(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """Assess ESG risk including climate transition and regulatory exposure."""
        pass

    @abstractmethod
    async def assess_tail_risk(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """Assess tail risk and black swan preparation."""
        pass


class ThematicInvestingStrategy(ABC):
    """Interface for thematic investing strategies."""

    @abstractmethod
    async def identify_themes(
        self,
        sources: list[str],
    ) -> list[dict[str, Any]]:
        """
        Identify investment themes using AI.

        NLP on analyst reports, academic papers, news.
        """
        pass

    @abstractmethod
    async def calculate_theme_purity(
        self,
        symbol: str,
        theme: str,
    ) -> float:
        """Calculate how exposed a company is to a specific theme."""
        pass

    @abstractmethod
    async def track_theme_lifecycle(
        self,
        theme: str,
    ) -> dict[str, Any]:
        """Track theme lifecycle and maturation stage."""
        pass

    @abstractmethod
    async def find_theme_exposures(
        self,
        symbols: list[str],
        themes: list[str],
    ) -> dict[str, Any]:
        """Find companies with exposure to specific themes."""
        pass


class MonitoringStrategy(ABC):
    """Interface for real-time monitoring strategies."""

    @abstractmethod
    async def setup_alerts(
        self,
        job_id: UUID,
        alert_config: dict[str, Any],
    ) -> None:
        """
        Setup real-time alerts.

        Alerts for:
        - Fundamental deterioration signals
        - Insider selling clusters
        - Social sentiment spikes
        - Supply chain disruptions
        - Price anomalies
        """
        pass

    @abstractmethod
    async def check_alerts(
        self,
        job_id: UUID,
    ) -> list[dict[str, Any]]:
        """Check active alerts for a job."""
        pass

    @abstractmethod
    async def generate_report(
        self,
        job: Job,
        format: str = "natural_language",
    ) -> str:
        """
        Generate automated report.

        Natural language summaries adapted to user's literacy level.
        """
        pass
