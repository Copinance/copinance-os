"""Static macro + market regime workflow executor.

This workflow is intentionally non-LLM and returns a combined payload containing:
- Macro regime indicators (rates, credit, commodities) preferring FRED
- Market regime indicators (VIX, breadth, sector rotation) + rule-based regime detections
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from copinanceos.domain.models.research import Research
from copinanceos.domain.models.tool_results import ToolResult
from copinanceos.domain.models.workflows import (
    AdvancedData,
    AnalysisMetadata,
    CommoditiesData,
    ConsumerData,
    CreditData,
    GlobalData,
    HousingData,
    LaborData,
    MacroRegimeIndicatorsData,
    MacroRegimeIndicatorsResult,
    MacroRegimeWorkflowResult,
    MacroSeriesMetadata,
    ManufacturingData,
    MarketCyclesData,
    MarketRegimeDetectionResult,
    MarketRegimeIndicatorsData,
    MarketRegimeIndicatorsResult,
    MarketTrendData,
    RatesData,
    VolatilityRegimeData,
)
from copinanceos.domain.ports.data_providers import MacroeconomicDataProvider, MarketDataProvider
from copinanceos.infrastructure.tools.analysis.market_regime import (
    create_market_regime_indicators_tool,
    create_market_regime_tools,
)
from copinanceos.infrastructure.tools.analysis.market_regime.macro_indicators import (
    create_macro_regime_indicators_tool,
)
from copinanceos.infrastructure.workflows.base import BaseWorkflowExecutor

logger = structlog.get_logger(__name__)


class MacroRegimeStaticWorkflowExecutor(BaseWorkflowExecutor):
    """Static workflow that returns macro data and market regime info together."""

    def __init__(
        self,
        market_data_provider: MarketDataProvider | None = None,
        macro_data_provider: MacroeconomicDataProvider | None = None,
    ) -> None:
        self._market_data_provider = market_data_provider
        self._macro_data_provider = macro_data_provider

    async def _execute_workflow(self, research: Research, context: dict[str, Any]) -> Any:
        if not self._market_data_provider:
            raise RuntimeError("MarketDataProvider not configured - required for macro workflow")
        if not self._macro_data_provider:
            raise RuntimeError(
                "MacroeconomicDataProvider not configured - required for macro workflow"
            )

        # Inputs
        # Research requires a symbol; users may pass MARKET as placeholder.
        market_index = str(context.get("market_index") or "").upper().strip()
        if not market_index:
            market_index = research.stock_symbol.upper().strip()
        if market_index in {"", "MARKET"}:
            market_index = "SPY"

        lookback_days = int(context.get("lookback_days", 252))
        include_vix = bool(context.get("include_vix", True))
        include_market_breadth = bool(context.get("include_market_breadth", True))
        include_sector_rotation = bool(context.get("include_sector_rotation", True))

        include_rates = bool(context.get("include_rates", True))
        include_credit = bool(context.get("include_credit", True))
        include_commodities = bool(context.get("include_commodities", True))
        include_labor = bool(context.get("include_labor", True))
        include_housing = bool(context.get("include_housing", True))
        include_manufacturing = bool(context.get("include_manufacturing", True))
        include_consumer = bool(context.get("include_consumer", True))
        include_global = bool(context.get("include_global", True))
        include_advanced = bool(context.get("include_advanced", True))

        # Market regime indicators (VIX, breadth, rotation)
        market_indicators_tool = create_market_regime_indicators_tool(self._market_data_provider)
        market_indicators_result = await market_indicators_tool.execute(
            market_index=market_index,
            lookback_days=lookback_days,
            include_vix=include_vix,
            include_market_breadth=include_market_breadth,
            include_sector_rotation=include_sector_rotation,
        )

        # Construct typed market regime indicators result
        market_indicators_data: MarketRegimeIndicatorsData | None = None
        if market_indicators_result.data:
            market_indicators_data = MarketRegimeIndicatorsData(
                vix=market_indicators_result.data.get("vix"),
                market_breadth=market_indicators_result.data.get("market_breadth"),
                sector_rotation=market_indicators_result.data.get("sector_rotation"),
            )

        market_regime_indicators = MarketRegimeIndicatorsResult(
            success=market_indicators_result.success,
            data=market_indicators_data,
            error=market_indicators_result.error,
            metadata=market_indicators_result.metadata or {},
        )

        # Rule-based regime detections (trend/vol/cycles) on the chosen market index
        # Fetch market data once and reuse for all regime detection tools to avoid duplicate API calls
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=lookback_days)
        regime_historical_data = None

        try:
            regime_historical_data = await self._market_data_provider.get_historical_data(
                symbol=market_index,
                start_date=start_date,
                end_date=end_date,
                interval="1d",
            )
        except Exception as e:
            logger.warning(
                "Failed to fetch market data for regime detection tools",
                market_index=market_index,
                error=str(e),
            )

        regime_tools = create_market_regime_tools(self._market_data_provider)
        regime_detection_data: dict[str, ToolResult] = {}

        for tool in regime_tools:
            tool_name = tool.get_name()
            try:
                # Pass pre-fetched data to avoid duplicate API calls
                tool_result = await tool.execute(
                    symbol=market_index,
                    lookback_days=lookback_days,
                    historical_data=regime_historical_data,
                )
                regime_detection_data[tool_name] = ToolResult(
                    success=tool_result.success,
                    data=tool_result.data,
                    error=tool_result.error,
                    metadata=tool_result.metadata,
                )
            except Exception as e:
                logger.warning(
                    "Regime detection tool failed",
                    tool=tool_name,
                    market_index=market_index,
                    error=str(e),
                )
                regime_detection_data[tool_name] = ToolResult(
                    success=False, data=None, error=str(e), metadata={}
                )

        detect_market_trend_result = regime_detection_data.get("detect_market_trend")
        detect_volatility_regime_result = regime_detection_data.get("detect_volatility_regime")
        detect_market_cycles_result = regime_detection_data.get("detect_market_cycles")

        # Construct proper model instances from tool result data
        detect_market_trend_data = None
        if detect_market_trend_result and detect_market_trend_result.data:
            data = detect_market_trend_result.data
            detect_market_trend_data = MarketTrendData(
                regime=data["regime"],
                confidence=data["confidence"],
                current_price=data["current_price"],
                price_change_pct=data["price_change_pct"],
                log_return=data["log_return"],
                volatility_scaled_momentum=data["volatility_scaled_momentum"],
                recent_volatility=data["recent_volatility"],
                momentum_20d_pct=data["momentum_20d_pct"],
                short_ma=data["short_ma"],
                long_ma=data["long_ma"],
                ma_relationship=data["ma_relationship"],
                short_ma_period_used=data["short_ma_period_used"],
                long_ma_period_used=data["long_ma_period_used"],
                methodology=data["methodology"],
                note=data.get("note"),
                metadata=AnalysisMetadata(
                    analysis_period_days=data["analysis_period_days"],
                    data_points=data["data_points"],
                    parameters_adjusted=data["parameters_adjusted"],
                ),
            )

        detect_volatility_regime_data = None
        if detect_volatility_regime_result and detect_volatility_regime_result.data:
            data = detect_volatility_regime_result.data
            detect_volatility_regime_data = VolatilityRegimeData(
                regime=data["regime"],
                current_volatility=data["current_volatility"],
                mean_volatility=data["mean_volatility"],
                max_volatility=data["max_volatility"],
                min_volatility=data["min_volatility"],
                volatility_percentile=data["volatility_percentile"],
                volatility_window=data["volatility_window"],
                metadata=AnalysisMetadata(
                    analysis_period_days=data["analysis_period_days"],
                    data_points=data["data_points"],
                    parameters_adjusted=data["parameters_adjusted"],
                ),
            )

        detect_market_cycles_data = None
        if detect_market_cycles_result and detect_market_cycles_result.data:
            data = detect_market_cycles_result.data
            detect_market_cycles_data = MarketCyclesData(
                current_phase=data["current_phase"],
                phase_description=data["phase_description"],
                price_position_pct=data["price_position_pct"],
                volume_ratio=data["volume_ratio"],
                current_price=data["current_price"],
                ma_20=data["ma_20"],
                ma_50=data["ma_50"],
                recent_trend=data["recent_trend"],
                longer_trend=data["longer_trend"],
                potential_regime_change=data["potential_regime_change"],
                ma_short_period_used=data["ma_short_period_used"],
                ma_long_period_used=data["ma_long_period_used"],
                metadata=AnalysisMetadata(
                    analysis_period_days=data["analysis_period_days"],
                    data_points=data["data_points"],
                    parameters_adjusted=data["parameters_adjusted"],
                ),
            )

        market_regime_detection = MarketRegimeDetectionResult(
            symbol=market_index,
            detect_market_trend=detect_market_trend_data,
            detect_volatility_regime=detect_volatility_regime_data,
            detect_market_cycles=detect_market_cycles_data,
        )

        # Macro regime indicators (FRED-first with yfinance fallbacks internally)
        macro_tool = create_macro_regime_indicators_tool(
            macro_data_provider=self._macro_data_provider,
            market_data_provider=self._market_data_provider,
        )
        macro_result = await macro_tool.execute(
            lookback_days=lookback_days,
            include_rates=include_rates,
            include_credit=include_credit,
            include_commodities=include_commodities,
            include_labor=include_labor,
            include_housing=include_housing,
            include_manufacturing=include_manufacturing,
            include_consumer=include_consumer,
            include_global=include_global,
            include_advanced=include_advanced,
        )

        # Construct typed macro regime indicators result
        macro_indicators_data: MacroRegimeIndicatorsData | None = None
        if macro_result.data:
            lookback_days = macro_result.metadata.get("lookback_days", 252)
            metadata = MacroSeriesMetadata(lookback_days=lookback_days)

            macro_indicators_data = MacroRegimeIndicatorsData(
                rates=(
                    RatesData(**macro_result.data.get("rates", {}), metadata=metadata)
                    if macro_result.data.get("rates")
                    else None
                ),
                credit=(
                    CreditData(**macro_result.data.get("credit", {}), metadata=metadata)
                    if macro_result.data.get("credit")
                    else None
                ),
                commodities=(
                    CommoditiesData(**macro_result.data.get("commodities", {}), metadata=metadata)
                    if macro_result.data.get("commodities")
                    else None
                ),
                labor=(
                    LaborData(**macro_result.data.get("labor", {}), metadata=metadata)
                    if macro_result.data.get("labor")
                    else None
                ),
                housing=(
                    HousingData(**macro_result.data.get("housing", {}), metadata=metadata)
                    if macro_result.data.get("housing")
                    else None
                ),
                manufacturing=(
                    ManufacturingData(
                        **macro_result.data.get("manufacturing", {}), metadata=metadata
                    )
                    if macro_result.data.get("manufacturing")
                    else None
                ),
                consumer=(
                    ConsumerData(**macro_result.data.get("consumer", {}), metadata=metadata)
                    if macro_result.data.get("consumer")
                    else None
                ),
                global_data=(
                    GlobalData(**macro_result.data.get("global", {}), metadata=metadata)
                    if macro_result.data.get("global")
                    else None
                ),
                advanced=(
                    AdvancedData(**macro_result.data.get("advanced", {}), metadata=metadata)
                    if macro_result.data.get("advanced")
                    else None
                ),
            )

        macro_regime_indicators = MacroRegimeIndicatorsResult(
            success=macro_result.success,
            data=macro_indicators_data,
            error=macro_result.error,
            metadata=MacroSeriesMetadata(
                lookback_days=macro_result.metadata.get("lookback_days", 252)
            ),
        )

        # Construct and return typed workflow result
        return MacroRegimeWorkflowResult(
            market_index=market_index,
            execution_timestamp=datetime.now(UTC),
            market_regime_indicators=market_regime_indicators,
            market_regime_detection=market_regime_detection,
            macro_regime_indicators=macro_regime_indicators,
            status=None,
            error=None,
        )

    async def validate(self, research: Research) -> bool:
        return research.workflow_type == "macro"

    def get_workflow_type(self) -> str:
        return "macro"
