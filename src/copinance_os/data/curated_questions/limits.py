"""Per-artifact JSON size caps for curated-questions LLM context."""

from __future__ import annotations

from copinance_os.domain.models.curated.questions import ArtifactType

# Max serialized summary JSON characters (after context build, before prompt).
ARTIFACT_MAX_JSON_CHARS: dict[ArtifactType, int] = {
    ArtifactType.OPTIONS_CHAIN: 12_000,
    ArtifactType.OPTIONS_POSITIONING: 10_000,
    ArtifactType.FUNDAMENTALS: 8_000,
    ArtifactType.HISTORICAL_BARS: 6_000,
    ArtifactType.WATCHLIST_RISK: 6_000,
    ArtifactType.SECTOR_ROTATION: 5_000,
    ArtifactType.UPCOMING_EVENTS: 5_000,
    ArtifactType.MARKET_REGIME: 4_000,
    ArtifactType.MACRO_SNAPSHOT: 4_000,
    ArtifactType.QUOTE: 3_000,
    ArtifactType.INSTRUMENT: 3_000,
}

DASHBOARD_ARTIFACTS: frozenset[ArtifactType] = frozenset(
    {
        ArtifactType.MARKET_REGIME,
        ArtifactType.MACRO_SNAPSHOT,
        ArtifactType.SECTOR_ROTATION,
        ArtifactType.UPCOMING_EVENTS,
        ArtifactType.WATCHLIST_RISK,
    }
)
