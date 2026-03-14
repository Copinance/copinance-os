"""Deterministic instrument analysis executor."""

from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from copinanceos.application.use_cases.analyze import INSTRUMENT_DETERMINISTIC_TYPE
from copinanceos.application.use_cases.fundamentals import (
    GetStockFundamentalsRequest,
    GetStockFundamentalsUseCase,
)
from copinanceos.application.use_cases.market import (
    GetHistoricalDataRequest,
    GetHistoricalDataUseCase,
    GetInstrumentRequest,
    GetInstrumentUseCase,
    GetOptionsChainRequest,
    GetOptionsChainUseCase,
    GetQuoteRequest,
    GetQuoteUseCase,
)
from copinanceos.domain.models.job import Job, JobScope, JobTimeframe
from copinanceos.domain.models.market import MarketType, OptionsChain, OptionSide
from copinanceos.infrastructure.cache import CacheManager
from copinanceos.infrastructure.executors.base import BaseAnalysisExecutor

logger = structlog.get_logger(__name__)


class InstrumentAnalysisExecutor(BaseAnalysisExecutor):
    """Executor for deterministic equity and options analysis."""

    def __init__(
        self,
        get_instrument_use_case: GetInstrumentUseCase | None = None,
        get_quote_use_case: GetQuoteUseCase | None = None,
        get_historical_data_use_case: GetHistoricalDataUseCase | None = None,
        get_options_chain_use_case: GetOptionsChainUseCase | None = None,
        fundamentals_use_case: GetStockFundamentalsUseCase | None = None,
        cache_manager: CacheManager | None = None,
    ) -> None:
        self._get_instrument_use_case = get_instrument_use_case
        self._get_quote_use_case = get_quote_use_case
        self._get_historical_data_use_case = get_historical_data_use_case
        self._get_options_chain_use_case = get_options_chain_use_case
        self._fundamentals_use_case = fundamentals_use_case
        self._cache_manager = cache_manager

    async def _execute_analysis(self, job: Job, context: dict[str, Any]) -> dict[str, Any]:
        if not job.instrument_symbol:
            raise ValueError("instrument_symbol is required for instrument analysis")

        symbol = job.instrument_symbol.upper()
        market_type = job.market_type or MarketType.EQUITY

        if market_type == MarketType.OPTIONS:
            return await self._execute_options_analysis(symbol, job.timeframe, context)
        return await self._execute_equity_analysis(symbol, job.timeframe)

    async def _execute_equity_analysis(
        self,
        symbol: str,
        timeframe: JobTimeframe,
    ) -> dict[str, Any]:
        instrument = await self._get_instrument_info(symbol)
        quote = await self._get_market_quote(symbol)
        historical_data = await self._get_historical_data(symbol, timeframe)
        fundamentals = await self._get_fundamentals(symbol, timeframe)
        analysis = await self._calculate_equity_analysis(
            symbol,
            quote,
            historical_data,
            fundamentals,
            timeframe,
        )

        return {
            "execution_type": "instrument_analysis",
            "execution_mode": "deterministic",
            "market_type": MarketType.EQUITY.value,
            "instrument": instrument,
            "current_quote": quote,
            "historical_data": historical_data,
            "fundamentals": fundamentals,
            "analysis": analysis,
            "summary": self._generate_equity_summary(
                instrument,
                quote,
                analysis,
                timeframe,
            ),
        }

    async def _execute_options_analysis(
        self,
        symbol: str,
        timeframe: JobTimeframe,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        if not self._get_options_chain_use_case:
            raise ValueError("GetOptionsChainUseCase not available for options analysis")

        expiration_date = context.get("expiration_date")
        requested_side = context.get("option_side", OptionSide.ALL.value)
        side = OptionSide(requested_side)

        quote = await self._get_market_quote(symbol)
        options_chain: OptionsChain | None = None
        if self._cache_manager:
            try:
                entry = await self._cache_manager.get(
                    "get_options_chain",
                    underlying_symbol=symbol,
                    expiration_date=expiration_date,
                )
                if entry and entry.data:
                    logger.info(
                        "Returning cached options chain",
                        underlying_symbol=symbol,
                        expiration_date=expiration_date,
                        cached_at=entry.cached_at.isoformat(),
                    )
                    options_chain = OptionsChain.model_validate(entry.data)
            except Exception as e:
                logger.debug(
                    "Cache lookup failed for options chain, fetching",
                    underlying_symbol=symbol,
                    error=str(e),
                )
        if options_chain is None:
            options_response = await self._get_options_chain_use_case.execute(
                GetOptionsChainRequest(
                    underlying_symbol=symbol,
                    expiration_date=expiration_date,
                )
            )
            options_chain = options_response.chain
            if self._cache_manager:
                try:
                    await self._cache_manager.set(
                        "get_options_chain",
                        data=options_chain.model_dump(mode="json"),
                        metadata={
                            "underlying_symbol": symbol,
                            "expiration_date": expiration_date,
                        },
                        underlying_symbol=symbol,
                        expiration_date=expiration_date,
                    )
                except Exception:
                    pass

        if side == OptionSide.CALL:
            selected_contracts = options_chain.calls
        elif side == OptionSide.PUT:
            selected_contracts = options_chain.puts
        else:
            selected_contracts = [*options_chain.calls, *options_chain.puts]

        underlying_price = float(options_chain.underlying_price or 0)
        total_open_interest = sum(contract.open_interest or 0 for contract in selected_contracts)
        total_volume = sum(contract.volume or 0 for contract in selected_contracts)
        iv_values = [
            float(contract.implied_volatility)
            for contract in selected_contracts
            if contract.implied_volatility is not None
        ]
        atm_contract = None
        if underlying_price > 0 and selected_contracts:
            atm_contract = min(
                selected_contracts,
                key=lambda contract: abs(float(contract.strike) - underlying_price),
            )

        analysis = {
            "symbol": symbol,
            "timeframe": timeframe.value,
            "expiration_date": options_chain.expiration_date.isoformat(),
            "side": side.value,
            "contracts_analyzed": len(selected_contracts),
            "metrics": {
                "underlying_price": (
                    str(options_chain.underlying_price)
                    if options_chain.underlying_price is not None
                    else None
                ),
                "total_open_interest": total_open_interest,
                "total_volume": total_volume,
                "average_implied_volatility": (
                    str(sum(iv_values) / len(iv_values)) if iv_values else None
                ),
                "put_call_open_interest_ratio": self._safe_ratio(
                    sum(contract.open_interest or 0 for contract in options_chain.puts),
                    sum(contract.open_interest or 0 for contract in options_chain.calls),
                ),
            },
            "at_the_money_contract": (
                {
                    "contract_symbol": atm_contract.contract_symbol,
                    "side": atm_contract.side.value,
                    "strike": str(atm_contract.strike),
                    "last_price": (
                        str(atm_contract.last_price)
                        if atm_contract.last_price is not None
                        else None
                    ),
                    "implied_volatility": (
                        str(atm_contract.implied_volatility)
                        if atm_contract.implied_volatility is not None
                        else None
                    ),
                    "open_interest": atm_contract.open_interest,
                    "volume": atm_contract.volume,
                }
                if atm_contract
                else None
            ),
        }

        contracts_preview = [
            {
                "contract_symbol": contract.contract_symbol,
                "side": contract.side.value,
                "strike": str(contract.strike),
                "last_price": str(contract.last_price) if contract.last_price is not None else None,
                "bid": str(contract.bid) if contract.bid is not None else None,
                "ask": str(contract.ask) if contract.ask is not None else None,
                "volume": contract.volume,
                "open_interest": contract.open_interest,
                "implied_volatility": (
                    str(contract.implied_volatility)
                    if contract.implied_volatility is not None
                    else None
                ),
                "in_the_money": contract.in_the_money,
            }
            for contract in selected_contracts[:10]
        ]

        return {
            "execution_type": "instrument_analysis",
            "execution_mode": "deterministic",
            "market_type": MarketType.OPTIONS.value,
            "current_quote": quote,
            "options_chain": {
                "underlying_symbol": options_chain.underlying_symbol,
                "expiration_date": options_chain.expiration_date.isoformat(),
                "available_expirations": [
                    expiration.isoformat() for expiration in options_chain.available_expirations
                ],
                "underlying_price": (
                    str(options_chain.underlying_price)
                    if options_chain.underlying_price is not None
                    else None
                ),
                "currency": options_chain.currency,
                "calls_count": len(options_chain.calls),
                "puts_count": len(options_chain.puts),
                "contracts_preview": contracts_preview,
                "metadata": options_chain.metadata,
            },
            "analysis": analysis,
            "summary": self._generate_options_summary(symbol, analysis),
        }

    async def _get_instrument_info(self, symbol: str) -> dict[str, Any]:
        if not self._get_instrument_use_case:
            logger.warning("GetInstrumentUseCase not available, skipping instrument info")
            return {"symbol": symbol, "note": "Instrument info not available"}

        try:
            response = await self._get_instrument_use_case.execute(
                GetInstrumentRequest(symbol=symbol)
            )
            if response.instrument:
                instrument = response.instrument
                return {
                    "symbol": instrument.symbol,
                    "name": instrument.name,
                    "exchange": instrument.exchange,
                    "sector": instrument.sector,
                    "industry": instrument.industry,
                    "market_cap": str(instrument.market_cap) if instrument.market_cap else None,
                    "currency": instrument.currency,
                }
            return {"symbol": symbol, "note": "Instrument not found in repository"}
        except Exception as e:
            logger.warning("Failed to get instrument info", symbol=symbol, error=str(e))
            return {"symbol": symbol, "error": str(e)}

    def _normalize_quote(self, quote: dict[str, Any], symbol: str) -> dict[str, Any]:
        """Build normalized quote dict from raw provider quote (for display/analysis)."""
        return {
            "symbol": quote.get("symbol", symbol),
            "current_price": str(quote.get("current_price", 0)),
            "previous_close": str(quote.get("previous_close", 0)),
            "open": str(quote.get("open", 0)),
            "high": str(quote.get("high", 0)),
            "low": str(quote.get("low", 0)),
            "volume": quote.get("volume", 0),
            "market_cap": quote.get("market_cap"),
            "currency": quote.get("currency", "USD"),
            "exchange": quote.get("exchange", ""),
            "timestamp": quote.get("timestamp"),
        }

    async def _get_market_quote(self, symbol: str) -> dict[str, Any]:
        if not self._get_quote_use_case:
            logger.warning("GetQuoteUseCase not available, skipping quote")
            return {"symbol": symbol, "note": "Quote not available"}

        symbol_upper = symbol.upper()
        if self._cache_manager:
            try:
                entry = await self._cache_manager.get("get_market_quote", symbol=symbol_upper)
                if entry and entry.data:
                    logger.info(
                        "Returning cached quote",
                        symbol=symbol_upper,
                        cached_at=entry.cached_at.isoformat(),
                    )
                    return self._normalize_quote(entry.data, symbol_upper)
            except Exception as e:
                logger.debug(
                    "Cache lookup failed for quote, fetching", symbol=symbol_upper, error=str(e)
                )

        try:
            response = await self._get_quote_use_case.execute(GetQuoteRequest(symbol=symbol_upper))
            quote = response.quote
            if self._cache_manager and quote:
                try:
                    await self._cache_manager.set(
                        "get_market_quote",
                        data=quote,
                        metadata={"symbol": symbol_upper},
                        symbol=symbol_upper,
                    )
                except Exception:
                    pass
            return self._normalize_quote(quote or {}, symbol_upper)
        except Exception as e:
            logger.warning("Failed to get market quote", symbol=symbol_upper, error=str(e))
            return {"symbol": symbol_upper, "error": str(e)}

    def _historical_data_to_summary(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        interval: str,
        data_points: list[Any],
    ) -> dict[str, Any]:
        """Build historical data summary from list of points (MarketDataPoint or serialized dicts)."""
        prices: list[float] = []
        volumes: list[int] = []
        for point in data_points:
            if hasattr(point, "close_price") and point.close_price is not None:
                prices.append(float(point.close_price))
            elif isinstance(point, dict) and point.get("close_price") is not None:
                try:
                    prices.append(float(point["close_price"]))
                except (TypeError, ValueError):
                    pass
            if hasattr(point, "volume"):
                volumes.append(point.volume)
            elif isinstance(point, dict) and point.get("volume") is not None:
                try:
                    volumes.append(int(point["volume"]))
                except (TypeError, ValueError):
                    pass

        price_stats: dict[str, str] = {}
        if prices:
            price_stats = {
                "current_price": str(prices[-1]),
                "period_start_price": str(prices[0]),
                "period_high": str(max(prices)),
                "period_low": str(min(prices)),
                "price_change": str(prices[-1] - prices[0]),
                "price_change_pct": (
                    str(((prices[-1] - prices[0]) / prices[0]) * 100) if prices[0] > 0 else "0"
                ),
            }
        volume_stats: dict[str, str] = {}
        if volumes:
            volume_stats = {
                "average_volume": str(sum(volumes) // len(volumes)),
                "max_volume": str(max(volumes)),
                "min_volume": str(min(volumes)),
            }
        return {
            "symbol": symbol,
            "data_points": len(data_points),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "interval": interval,
            "price_statistics": price_stats,
            "volume_statistics": volume_stats,
        }

    async def _get_historical_data(self, symbol: str, timeframe: JobTimeframe) -> dict[str, Any]:
        if not self._get_historical_data_use_case:
            logger.warning("GetHistoricalDataUseCase not available, skipping historical data")
            return {"symbol": symbol, "note": "Historical data not available"}

        symbol_upper = symbol.upper()
        try:
            end_date = datetime.now(UTC)
            if timeframe == JobTimeframe.SHORT_TERM:
                start_date = end_date - timedelta(days=30)
                interval = "1d"
            elif timeframe == JobTimeframe.MID_TERM:
                start_date = end_date - timedelta(days=180)
                interval = "1d"
            else:
                start_date = end_date - timedelta(days=365 * 2)
                interval = "1wk"

            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            if self._cache_manager:
                try:
                    entry = await self._cache_manager.get(
                        "get_historical_market_data",
                        symbol=symbol_upper,
                        start_date=start_str,
                        end_date=end_str,
                        interval=interval,
                    )
                    if entry and entry.data:
                        logger.info(
                            "Returning cached historical data",
                            symbol=symbol_upper,
                            cached_at=entry.cached_at.isoformat(),
                        )
                        return self._historical_data_to_summary(
                            symbol_upper, start_date, end_date, interval, entry.data or []
                        )
                except Exception as e:
                    logger.debug(
                        "Cache lookup failed for historical data, fetching",
                        symbol=symbol_upper,
                        error=str(e),
                    )

            response = await self._get_historical_data_use_case.execute(
                GetHistoricalDataRequest(
                    symbol=symbol_upper,
                    start_date=start_date,
                    end_date=end_date,
                    interval=interval,
                )
            )
            historical = response.data

            if self._cache_manager and historical:
                try:
                    serialized = [
                        p.model_dump(mode="json") if hasattr(p, "model_dump") else p
                        for p in historical
                    ]
                    await self._cache_manager.set(
                        "get_historical_market_data",
                        data=serialized,
                        metadata={
                            "symbol": symbol_upper,
                            "start_date": start_str,
                            "end_date": end_str,
                            "interval": interval,
                        },
                        symbol=symbol_upper,
                        start_date=start_str,
                        end_date=end_str,
                        interval=interval,
                    )
                except Exception:
                    pass

            if not historical:
                return {
                    "symbol": symbol_upper,
                    "data_points": 0,
                    "note": "No historical data available",
                }

            return self._historical_data_to_summary(
                symbol_upper, start_date, end_date, interval, historical
            )
        except Exception as e:
            logger.warning("Failed to get historical data", symbol=symbol_upper, error=str(e))
            return {"symbol": symbol_upper, "error": str(e)}

    def _normalize_fundamentals_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """Build executor-style fundamentals dict from cached or use-case response (serialized dict)."""
        ratios_raw = data.get("ratios") or {}
        ratios_dict: dict[str, Any] = {}
        for k, v in ratios_raw.items():
            if v is None:
                continue
            ratios_dict[k] = v if k == "metadata" and isinstance(v, dict) else str(v)
        out: dict[str, Any] = {
            "symbol": data.get("symbol"),
            "company_name": data.get("company_name"),
            "sector": data.get("sector"),
            "industry": data.get("industry"),
            "provider": data.get("provider"),
            "data_as_of": (
                data["data_as_of"].isoformat()
                if hasattr(data.get("data_as_of"), "isoformat")
                else data.get("data_as_of")
            ),
            "currency": data.get("currency"),
            "fiscal_year_end": data.get("fiscal_year_end"),
            "market_cap": str(data["market_cap"]) if data.get("market_cap") is not None else None,
            "enterprise_value": (
                str(data["enterprise_value"]) if data.get("enterprise_value") is not None else None
            ),
            "current_price": (
                str(data["current_price"]) if data.get("current_price") is not None else None
            ),
            "shares_outstanding": data.get("shares_outstanding"),
            "float_shares": data.get("float_shares"),
            "metadata": data.get("metadata"),
        }
        if ratios_dict:
            out["ratios"] = ratios_dict
        return out

    async def _get_fundamentals(self, symbol: str, timeframe: JobTimeframe) -> dict[str, Any]:
        if not self._fundamentals_use_case:
            logger.warning("FundamentalsUseCase not available, skipping fundamentals")
            return {"symbol": symbol, "note": "Fundamentals not available"}

        symbol_upper = symbol.upper()
        try:
            if timeframe == JobTimeframe.SHORT_TERM:
                periods = 4
                period_type = "quarterly"
            elif timeframe == JobTimeframe.MID_TERM:
                periods = 8
                period_type = "quarterly"
            else:
                periods = 5
                period_type = "annual"

            if self._cache_manager:
                try:
                    entry = await self._cache_manager.get(
                        "get_equity_fundamentals",
                        symbol=symbol_upper,
                        periods=periods,
                        period_type=period_type,
                    )
                    if entry and entry.data:
                        logger.info(
                            "Returning cached fundamentals",
                            symbol=symbol_upper,
                            cached_at=entry.cached_at.isoformat(),
                        )
                        return self._normalize_fundamentals_dict(dict(entry.data))
                except Exception as e:
                    logger.debug(
                        "Cache lookup failed for fundamentals, fetching",
                        symbol=symbol_upper,
                        error=str(e),
                    )

            response = await self._fundamentals_use_case.execute(
                GetStockFundamentalsRequest(
                    symbol=symbol_upper,
                    periods=periods,
                    period_type=period_type,
                )
            )
            fundamentals = response.fundamentals
            fundamentals_dict = self._normalize_fundamentals_dict(
                fundamentals.model_dump(mode="json")
            )

            if self._cache_manager:
                try:
                    await self._cache_manager.set(
                        "get_equity_fundamentals",
                        data=fundamentals.model_dump(mode="json"),
                        metadata={
                            "symbol": symbol_upper,
                            "periods": periods,
                            "period_type": period_type,
                        },
                        symbol=symbol_upper,
                        periods=periods,
                        period_type=period_type,
                    )
                except Exception:
                    pass
            return fundamentals_dict
        except Exception as e:
            logger.warning("Failed to get fundamentals", symbol=symbol_upper, error=str(e))
            return {"symbol": symbol_upper, "error": str(e)}

    async def _calculate_equity_analysis(
        self,
        symbol: str,
        quote: dict[str, Any],
        historical_data: dict[str, Any],
        fundamentals: dict[str, Any],
        timeframe: JobTimeframe,
    ) -> dict[str, Any]:
        analysis: dict[str, Any] = {
            "symbol": symbol,
            "timeframe": timeframe.value,
            "metrics": {},
            "trends": {},
            "assessments": [],
        }

        if historical_data.get("price_statistics"):
            price_stats = historical_data["price_statistics"]
            price_change_pct = float(price_stats.get("price_change_pct", 0))
            analysis["trends"]["price_trend"] = {
                "direction": "up" if price_change_pct > 0 else "down",
                "magnitude": abs(price_change_pct),
                "change_pct": str(price_change_pct),
            }

        if fundamentals.get("ratios"):
            ratios = fundamentals["ratios"]
            analysis["metrics"]["valuation"] = {
                "pe_ratio": ratios.get("price_to_earnings"),
                "pb_ratio": ratios.get("price_to_book"),
                "ps_ratio": ratios.get("price_to_sales"),
                "ev_ebitda": ratios.get("enterprise_value_to_ebitda"),
            }
            analysis["metrics"]["profitability"] = {
                "gross_margin": ratios.get("gross_margin"),
                "operating_margin": ratios.get("operating_margin"),
                "net_margin": ratios.get("net_margin"),
                "roe": ratios.get("return_on_equity"),
                "roa": ratios.get("return_on_assets"),
            }
            analysis["metrics"]["financial_health"] = {
                "current_ratio": ratios.get("current_ratio"),
                "quick_ratio": ratios.get("quick_ratio"),
                "debt_to_equity": ratios.get("debt_to_equity"),
                "interest_coverage": ratios.get("interest_coverage"),
            }
            analysis["metrics"]["growth"] = {
                "revenue_growth": ratios.get("revenue_growth"),
                "earnings_growth": ratios.get("earnings_growth"),
                "fcf_growth": ratios.get("free_cash_flow_growth"),
            }

        assessments = analysis["assessments"]
        if quote.get("current_price") and historical_data.get("price_statistics"):
            current_price = float(quote["current_price"])
            period_high = float(historical_data["price_statistics"].get("period_high", 0))
            period_low = float(historical_data["price_statistics"].get("period_low", 0))
            if period_high > period_low:
                price_position = (current_price - period_low) / (period_high - period_low)
                if price_position > 0.8:
                    assessments.append("Trading near the upper end of the selected range")
                elif price_position < 0.2:
                    assessments.append("Trading near the lower end of the selected range")

        current_ratio = fundamentals.get("ratios", {}).get("current_ratio")
        if current_ratio:
            current_ratio_value = float(current_ratio)
            if current_ratio_value < 1.0:
                assessments.append("Liquidity is tight based on the current ratio")
            elif current_ratio_value > 2.0:
                assessments.append("Liquidity looks strong based on the current ratio")

        return analysis

    def _generate_equity_summary(
        self,
        instrument: dict[str, Any],
        quote: dict[str, Any],
        analysis: dict[str, Any],
        timeframe: JobTimeframe,
    ) -> dict[str, Any]:
        summary_parts = []
        if instrument.get("name"):
            summary_parts.append(f"Instrument: {instrument['name']}")
        if instrument.get("sector"):
            summary_parts.append(f"Sector: {instrument['sector']}")
        if quote.get("current_price"):
            summary_parts.append(f"Current Price: {quote['current_price']}")
        if analysis.get("trends", {}).get("price_trend"):
            trend = analysis["trends"]["price_trend"]
            summary_parts.append(
                f"Price Trend ({timeframe.value}): {trend['direction']} {trend['magnitude']:.2f}%"
            )
        pe_ratio = analysis.get("metrics", {}).get("valuation", {}).get("pe_ratio")
        if pe_ratio:
            summary_parts.append(f"P/E Ratio: {pe_ratio}")
        roe = analysis.get("metrics", {}).get("profitability", {}).get("roe")
        if roe:
            summary_parts.append(f"ROE: {roe}%")
        for assessment in analysis.get("assessments", []):
            summary_parts.append(f"- {assessment}")

        return {
            "text": "\n".join(summary_parts),
            "timeframe": timeframe.value,
            "analysis_date": datetime.now(UTC).isoformat(),
        }

    def _generate_options_summary(self, symbol: str, analysis: dict[str, Any]) -> dict[str, Any]:
        metrics = analysis["metrics"]
        summary_parts = [
            f"Options snapshot for {symbol}",
            f"Expiration: {analysis['expiration_date']}",
            f"Contracts analyzed: {analysis['contracts_analyzed']}",
        ]
        if metrics.get("underlying_price"):
            summary_parts.append(f"Underlying Price: {metrics['underlying_price']}")
        if metrics.get("put_call_open_interest_ratio"):
            summary_parts.append(
                f"Put/Call Open Interest Ratio: {metrics['put_call_open_interest_ratio']}"
            )
        if metrics.get("average_implied_volatility"):
            summary_parts.append(
                f"Average Implied Volatility: {metrics['average_implied_volatility']}"
            )
        return {
            "text": "\n".join(summary_parts),
            "timeframe": analysis["timeframe"],
            "analysis_date": datetime.now(UTC).isoformat(),
        }

    def _safe_ratio(self, numerator: int, denominator: int) -> str | None:
        if denominator <= 0:
            return None
        return str(numerator / denominator)

    async def validate(self, job: Job) -> bool:
        return (
            job.scope == JobScope.INSTRUMENT
            and job.execution_type == INSTRUMENT_DETERMINISTIC_TYPE
            and bool(job.instrument_symbol)
        )

    def get_executor_id(self) -> str:
        return "instrument_analysis"
