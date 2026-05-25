"""Domain models for LLM-generated market narratives."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from copinance_os.domain.models.profile import FinancialLiteracy


class MarketNarrativeRequest(BaseModel):
    """Request to generate a short LLM prose summary of current market conditions.

    The narrative is grounded in the deterministic market analysis output (regime,
    volatility, macro indicators) and adapted to the caller's literacy level.  No
    external data is fetched beyond what the standard market analysis already uses.

    Library usage::

        from copinance_os import MarketNarrativeRequest, FinancialLiteracy
        from copinance_os.infra.di import get_container

        container = get_container(llm_config=my_llm_config)
        use_case = container.generate_market_narrative_use_case()
        result = await use_case.execute(
            MarketNarrativeRequest(
                market_index="SPY",
                financial_literacy=FinancialLiteracy.BEGINNER,
            )
        )
        print(result.narrative)
    """

    market_index: str = Field("SPY", description="Market index symbol (e.g. SPY, QQQ)")
    financial_literacy: FinancialLiteracy = Field(
        FinancialLiteracy.INTERMEDIATE,
        description="Literacy tier for tone and vocabulary of the narrative",
    )
    no_cache: bool = Field(
        False,
        description="When True, bypass the internal market analysis cache for this run",
    )


class NarrativeResult(BaseModel):
    """Result of a market narrative generation request.

    The ``narrative`` field contains 2–3 sentences adapted to the requested
    literacy level.  When the LLM is unavailable (no config, circuit open, or
    error) ``fallback=True`` and the narrative is produced deterministically from
    the regime labels instead.
    """

    narrative: str = Field(..., description="2–3 sentence market narrative prose")
    literacy: FinancialLiteracy = Field(
        ..., description="Literacy level used (echoed for consumer cache keying)"
    )
    market_index: str = Field(..., description="Market index that was analysed")
    generated_at: datetime = Field(..., description="UTC timestamp of generation")
    fallback: bool = Field(
        False,
        description="True when the LLM was unavailable and a deterministic template was used",
    )
