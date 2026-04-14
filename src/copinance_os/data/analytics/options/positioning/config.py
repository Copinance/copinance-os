"""Bundled methodology configs for aggregate positioning (per-sub-computation overrides)."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any

from copinance_os.data.analytics.options.positioning.bias import (
    DEFAULT_BIAS_CONFIG,
    BiasConfig,
    bias_methodology,
)
from copinance_os.data.analytics.options.positioning.charm import (
    DEFAULT_CHARM_CONFIG,
    CharmConfig,
    charm_methodology,
)
from copinance_os.data.analytics.options.positioning.delta import (
    DEFAULT_DELTA_CONFIG,
    DeltaConfig,
    delta_methodology,
)
from copinance_os.data.analytics.options.positioning.dollar import (
    DEFAULT_DOLLAR_CONFIG,
    DollarConfig,
    dollar_methodology,
)
from copinance_os.data.analytics.options.positioning.flow import (
    DEFAULT_FLOW_CONFIG,
    FlowConfig,
    flow_methodology,
)
from copinance_os.data.analytics.options.positioning.gex import (
    DEFAULT_GEX_CONFIG,
    GexConfig,
    gex_methodology,
)
from copinance_os.data.analytics.options.positioning.implied_move import (
    DEFAULT_IMPLIED_MOVE_CONFIG,
    ImpliedMoveConfig,
    implied_move_methodology,
)
from copinance_os.data.analytics.options.positioning.mispricing import (
    DEFAULT_MISPRICING_CONFIG,
    MispricingConfig,
    mispricing_methodology,
)
from copinance_os.data.analytics.options.positioning.moneyness import (
    DEFAULT_MONEYNESS_CONFIG,
    MoneynessConfig,
    moneyness_methodology,
)
from copinance_os.data.analytics.options.positioning.oi_clusters import (
    DEFAULT_OI_CLUSTERS_CONFIG,
    OiClustersConfig,
    oi_clusters_methodology,
)
from copinance_os.data.analytics.options.positioning.pin_risk import (
    DEFAULT_PIN_RISK_CONFIG,
    PinRiskConfig,
    pin_risk_methodology,
)
from copinance_os.data.analytics.options.positioning.quality import (
    DEFAULT_DATA_QUALITY_CONFIG,
    DataQualityConfig,
    data_quality_methodology,
)
from copinance_os.data.analytics.options.positioning.surface import (
    DEFAULT_SURFACE_CONFIG,
    SurfaceConfig,
    surface_methodology,
)
from copinance_os.data.analytics.options.positioning.vanna import (
    DEFAULT_VANNA_CONFIG,
    VannaConfig,
    vanna_methodology,
)
from copinance_os.data.analytics.options.positioning.volatility import (
    DEFAULT_VOLATILITY_CONFIG,
    VolatilityConfig,
    volatility_methodology,
)
from copinance_os.domain.models.methodology import MethodologySpec


@dataclass(frozen=True, slots=True)
class BsmGreeksConfig:
    """Reserved for future explicit Greek-engine tuning at the positioning bundle level."""

    note: str = "resolved_at_enrichment"


DEFAULT_BSM_GREEKS_CONFIG = BsmGreeksConfig()


@dataclass(frozen=True, slots=True)
class PositioningMethodology:
    bias: BiasConfig = DEFAULT_BIAS_CONFIG
    gex: GexConfig = DEFAULT_GEX_CONFIG
    vanna: VannaConfig = DEFAULT_VANNA_CONFIG
    charm: CharmConfig = DEFAULT_CHARM_CONFIG
    pin_risk: PinRiskConfig = DEFAULT_PIN_RISK_CONFIG
    moneyness: MoneynessConfig = DEFAULT_MONEYNESS_CONFIG
    flow: FlowConfig = DEFAULT_FLOW_CONFIG
    volatility: VolatilityConfig = DEFAULT_VOLATILITY_CONFIG
    surface: SurfaceConfig = DEFAULT_SURFACE_CONFIG
    mispricing: MispricingConfig = DEFAULT_MISPRICING_CONFIG
    quality: DataQualityConfig = DEFAULT_DATA_QUALITY_CONFIG
    implied_move: ImpliedMoveConfig = DEFAULT_IMPLIED_MOVE_CONFIG
    dollar: DollarConfig = DEFAULT_DOLLAR_CONFIG
    delta: DeltaConfig = DEFAULT_DELTA_CONFIG
    oi_clusters: OiClustersConfig = DEFAULT_OI_CLUSTERS_CONFIG
    greeks: BsmGreeksConfig = DEFAULT_BSM_GREEKS_CONFIG

    def with_overrides(self, **overrides: Any) -> PositioningMethodology:
        data = {f.name: getattr(self, f.name) for f in fields(self)}
        for k, v in overrides.items():
            if k in data:
                data[k] = v
        return PositioningMethodology(**data)

    def specs(self) -> tuple[MethodologySpec, ...]:
        return (
            data_quality_methodology(self.quality),
            dollar_methodology(self.dollar),
            delta_methodology(self.delta),
            gex_methodology(self.gex),
            vanna_methodology(self.vanna),
            charm_methodology(self.charm),
            mispricing_methodology(self.mispricing),
            moneyness_methodology(self.moneyness),
            pin_risk_methodology(self.pin_risk),
            volatility_methodology(self.volatility),
            surface_methodology(self.surface),
            flow_methodology(self.flow),
            implied_move_methodology(self.implied_move),
            oi_clusters_methodology(self.oi_clusters),
            bias_methodology(self.bias),
        )


DEFAULT_POSITIONING_METHODOLOGY = PositioningMethodology()
