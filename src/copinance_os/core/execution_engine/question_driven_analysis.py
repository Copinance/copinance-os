"""Question-driven analysis executor implementation."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog

from copinance_os.ai.llm.policy import NUMERIC_GROUNDING_POLICY
from copinance_os.ai.llm.resources import (
    ANALYZE_QUESTION_DRIVEN_PROMPT_NAME,
    PromptManager,
)
from copinance_os.core.execution_engine.base import BaseAnalysisExecutor
from copinance_os.core.execution_engine.llm_stream_stdout import stdout_llm_stream_handler
from copinance_os.core.pipeline.tools import (
    create_fundamental_data_tools,
    create_fundamental_data_tools_with_providers,
    create_macro_regime_indicators_tool,
    create_market_data_tools,
    create_rule_based_regime_tools,
)
from copinance_os.core.pipeline.tools.analysis.market_regime.indicators import (
    create_market_regime_indicators_tool,
)
from copinance_os.core.pipeline.tools.context_tools import GetCurrentDateTool
from copinance_os.domain.models.job import Job, JobScope
from copinance_os.domain.models.llm_conversation import parse_conversation_history
from copinance_os.domain.models.market import MarketType
from copinance_os.domain.ports.analyzers import LLMAnalyzer
from copinance_os.domain.ports.data_providers import (
    FundamentalDataProvider,
    MacroeconomicDataProvider,
    MarketDataProvider,
)
from copinance_os.domain.ports.tools import Tool
from copinance_os.research.workflows.analyze import (
    INSTRUMENT_QUESTION_DRIVEN_TYPE,
    MARKET_QUESTION_DRIVEN_TYPE,
)

logger = structlog.get_logger(__name__)

QUESTION_ANALYSIS_PROMPT_CACHE_NAME = "question_analysis_prompt"


class QuestionDrivenAnalysisExecutor(BaseAnalysisExecutor):
    """Executor for question-driven analysis. Uses LLM with tools to perform AI-powered analysis."""

    def __init__(
        self,
        llm_analyzer: LLMAnalyzer | None = None,
        market_data_provider: MarketDataProvider | None = None,
        macro_data_provider: MacroeconomicDataProvider | None = None,
        fundamental_data_provider: FundamentalDataProvider | None = None,
        sec_filings_provider: FundamentalDataProvider | None = None,
        prompt_manager: PromptManager | None = None,
        cache_manager: Any | None = None,  # CacheManager type, avoiding circular import
    ) -> None:
        """Initialize question-driven analysis executor.

        Args:
            llm_analyzer: Optional LLM analyzer. If None, executor will work without LLM.
            market_data_provider: Optional market data provider for tools.
            fundamental_data_provider: Optional fundamental data provider for tools.
            sec_filings_provider: Optional separate provider for SEC filings. If provided,
                                 SEC filings tools use this provider instead of fundamental_data_provider.
            prompt_manager: Optional prompt manager. If None, creates a default one.
            cache_manager: Optional cache manager for tool caching.
        """
        self._llm_analyzer = llm_analyzer
        self._market_data_provider = market_data_provider
        self._macro_data_provider = macro_data_provider
        self._fundamental_data_provider = fundamental_data_provider
        self._sec_filings_provider = sec_filings_provider
        self._prompt_manager = prompt_manager or PromptManager()
        self._cache_manager = cache_manager

    async def _execute_analysis(self, job: Job, context: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a question-driven analysis using LLM with tools.

        This executor uses LLM analyzers with data provider tools to perform
        dynamic AI-powered analysis. The LLM can fetch real-time data and
        provide comprehensive answers to questions about stocks.

        Args:
            job: The job to execute
            context: Execution context and parameters. Can include:
                - "question": Specific question to answer (optional)
                - "conversation_history": Prior turns as
                  ``[{"role":"user"|"assistant","content": str}, ...]`` (optional).
                  Must be alternating user/assistant and end with assistant; the new
                  user message is ``question``.
                - "financial_literacy": User's financial literacy level (optional)

        Returns:
            Results dictionary containing analysis outputs including:
                - analysis: LLM's analysis text
                - tool_calls: Tools that were used
                - iterations: Number of LLM iterations
                - conversation_turns: Full user/assistant transcript after success (for follow-up jobs)
        """
        is_market_wide = job.scope == JobScope.MARKET
        market_type = job.market_type or MarketType.EQUITY
        # Use a sensible default symbol for tool examples and prompt context.
        # For market-wide questions, we anchor to a market index (default: SPY).
        symbol = (
            (job.market_index or "SPY").upper()
            if is_market_wide
            else (job.instrument_symbol or "").upper()
        )
        if not is_market_wide and not symbol:
            raise ValueError(
                "instrument_symbol is required for question-driven analysis when scope=instrument"
            )

        results: dict[str, Any] = {}

        # Check if LLM analyzer is available
        if self._llm_analyzer is None:
            results["status"] = "failed"
            results["error"] = "LLM analyzer not configured"
            results["message"] = "LLM analyzer is required for question-driven analysis"
            logger.warning("Question-driven analysis executed without LLM analyzer")
            return results

        # Get LLM provider from analyzer
        llm_provider = self._llm_analyzer._llm_provider  # type: ignore[attr-defined]

        # Check if provider supports tools
        if not hasattr(llm_provider, "generate_with_tools"):
            results["status"] = "failed"
            results["error"] = "LLM provider does not support tools"
            results["message"] = (
                f"Provider {llm_provider.get_provider_name()} does not support tool calling"
            )
            logger.warning(
                "LLM provider does not support tools", provider=llm_provider.get_provider_name()
            )
            return results

        # Create tools: always include current-date tool so LLM can get today's date
        tools: list = [GetCurrentDateTool()]
        logger.debug(
            "Creating tools",
            has_cache_manager=self._cache_manager is not None,
            has_sec_filings_provider=self._sec_filings_provider is not None,
        )
        if self._market_data_provider:
            market_tools = create_market_data_tools(
                self._market_data_provider, cache_manager=self._cache_manager
            )
            tools.extend(market_tools)
            logger.debug(
                "Added market data tools",
                count=len(market_tools),
                cache_enabled=self._cache_manager is not None,
            )

            # Add market regime detection tools
            regime_tools = create_rule_based_regime_tools(self._market_data_provider)
            tools.extend(regime_tools)

            # Add market regime indicators tool
            indicators_tool = create_market_regime_indicators_tool(
                self._market_data_provider,
                cache_manager=self._cache_manager,
            )
            tools.append(indicators_tool)

            # Add macro regime indicators tool (rates/credit/commodities) if configured
            if self._macro_data_provider:
                macro_tool = create_macro_regime_indicators_tool(
                    self._macro_data_provider,
                    self._market_data_provider,
                    cache_manager=self._cache_manager,
                )
                tools.append(macro_tool)

            logger.debug(
                "Added market regime detection tools and indicators",
                regime_tools_count=len(regime_tools),
                indicators_tool=True,
                macro_tool=bool(self._macro_data_provider),
            )

        if self._fundamental_data_provider:
            # Use provider selection if SEC filings provider is specified
            if self._sec_filings_provider:
                fundamental_tools = create_fundamental_data_tools_with_providers(
                    default_provider=self._fundamental_data_provider,
                    sec_filings_provider=self._sec_filings_provider,
                    cache_manager=self._cache_manager,
                )
                logger.info(
                    "Added fundamental data tools with provider selection",
                    count=len(fundamental_tools),
                    default_provider=self._fundamental_data_provider.get_provider_name(),
                    sec_filings_provider=self._sec_filings_provider.get_provider_name(),
                    cache_enabled=self._cache_manager is not None,
                )
            else:
                fundamental_tools = create_fundamental_data_tools(
                    self._fundamental_data_provider, cache_manager=self._cache_manager
                )
                logger.debug(
                    "Added fundamental data tools",
                    count=len(fundamental_tools),
                    cache_enabled=self._cache_manager is not None,
                )
            tools.extend(fundamental_tools)

        if not tools:
            results["status"] = "failed"
            results["error"] = "No data providers configured"
            results["message"] = (
                "At least one data provider is required for question-driven analysis"
            )
            logger.warning("No tools available for question-driven analysis")
            return results

        # Validate that question is provided
        question = context.get("question")
        if not question:
            results["status"] = "failed"
            results["error"] = "Question is required"
            results["message"] = (
                f"A question is required for question-driven analysis. What is your question about {symbol}?"
            )
            logger.warning("Question-driven analysis executed without question", symbol=symbol)
            return results

        try:
            prior_turns = parse_conversation_history(context.get("conversation_history"))
        except ValueError as e:
            results["status"] = "failed"
            results["error"] = "Invalid conversation_history"
            results["message"] = str(e)
            logger.warning("Invalid conversation history", error=str(e))
            return results

        conversation_history_digest = (
            json.dumps([t.model_dump() for t in prior_turns], ensure_ascii=False)
            if prior_turns
            else ""
        )

        # Enhance question to include symbol/index context when helpful.
        enhanced_question = question
        if is_market_wide:
            # Avoid forcing a fake "symbol" into the question. Just provide anchor context.
            if symbol and symbol.upper() not in question.upper():
                enhanced_question = f"Market-wide (anchor index: {symbol}): {question}"
        else:
            # This helps the LLM know which instrument to use in tool calls.
            if symbol.upper() not in question.upper():
                enhanced_question = f"About {market_type.value} instrument {symbol}: {question}"

            if market_type == MarketType.OPTIONS:
                option_context_parts = []
                if context.get("expiration_date"):
                    option_context_parts.append(f"expiration {context['expiration_date']}")
                if context.get("option_side") and context["option_side"] != "all":
                    option_context_parts.append(f"side {context['option_side']}")
                if option_context_parts:
                    enhanced_question = (
                        f"{enhanced_question} (options context: {', '.join(option_context_parts)})"
                    )

        # Current date so the LLM can compute relative ranges (e.g. "last year" = today minus 1 year)
        today = datetime.now(UTC).date()
        current_date = today.isoformat()

        # Build tool descriptions and examples (use current_date for date param examples)
        tools_description, tool_examples = self._build_tool_descriptions(
            tools, symbol, current_date=current_date
        )

        # Get financial literacy level
        financial_literacy = context.get("financial_literacy", "intermediate")

        # Load prompts: use cache when available, otherwise render and cache
        cache_kw = {
            "prompt_name": ANALYZE_QUESTION_DRIVEN_PROMPT_NAME,
            "question": enhanced_question,
            "tools_description": tools_description,
            "tool_examples": tool_examples,
            "financial_literacy": financial_literacy,
            "current_date": current_date,
            "conversation_history_digest": conversation_history_digest,
        }
        system_prompt = ""
        user_prompt = ""
        if self._cache_manager:
            entry = await self._cache_manager.get(QUESTION_ANALYSIS_PROMPT_CACHE_NAME, **cache_kw)
            if entry and isinstance(entry.data, dict):
                system_prompt = entry.data.get("system_prompt", "") or ""
                user_prompt = entry.data.get("user_prompt", "") or ""
                if system_prompt and user_prompt:
                    logger.debug("Using cached prompts for question-driven analysis", symbol=symbol)
        if not system_prompt or not user_prompt:
            system_prompt, user_prompt = self._prompt_manager.get_prompt(
                ANALYZE_QUESTION_DRIVEN_PROMPT_NAME,
                question=enhanced_question,
                tools_description=tools_description,
                tool_examples=tool_examples,
                financial_literacy=financial_literacy,
                current_date=current_date,
            )
            if self._cache_manager:
                await self._cache_manager.set(
                    QUESTION_ANALYSIS_PROMPT_CACHE_NAME,
                    {"system_prompt": system_prompt, "user_prompt": user_prompt},
                    **cache_kw,
                )

        logger.info(
            "Executing question-driven analysis with tools",
            symbol=symbol,
            tool_count=len(tools),
            provider=llm_provider.get_provider_name(),
        )

        stream = bool(context.get("stream"))
        on_stream = context.get("on_llm_stream")
        if stream and on_stream is None:
            on_stream = stdout_llm_stream_handler

        # Execute LLM with tools
        llm_result = await llm_provider.generate_with_tools(
            prompt=user_prompt,
            tools=tools,
            system_prompt=system_prompt,
            temperature=0.7,
            max_iterations=5,
            stream=stream,
            on_stream_event=on_stream if stream else None,
            prior_conversation=prior_turns if prior_turns else None,
        )

        # Extract results
        results["analysis"] = llm_result.get("text", "")
        if stream:
            results["analysis_streamed"] = True
        results["tool_calls"] = llm_result.get("tool_calls", [])
        results["iterations"] = llm_result.get("iterations", 1)
        results["llm_provider"] = llm_provider.get_provider_name()
        results["llm_model"] = llm_provider.get_model_name()
        results["tools_used"] = [tc.get("tool") for tc in results["tool_calls"]]
        results["numeric_grounding_policy"] = NUMERIC_GROUNDING_POLICY
        synthesis_status = llm_result.get("synthesis_status")
        if synthesis_status:
            results["synthesis_status"] = synthesis_status
        if llm_result.get("llm_synthesis_error"):
            results["llm_synthesis_error"] = llm_result["llm_synthesis_error"]
        if synthesis_status == "partial":
            results["message"] = (
                "Analysis completed with a deterministic data summary "
                "(the model did not return a final narrative; see analysis text)."
            )
        if llm_result.get("llm_usage"):
            results["llm_usage"] = llm_result["llm_usage"]
        if context.get("include_prompt"):
            results["system_prompt"] = system_prompt
            results["user_prompt"] = user_prompt

        analysis_text = (results.get("analysis") or "").strip()
        if analysis_text:
            results["conversation_turns"] = [
                *[t.model_dump() for t in prior_turns],
                {"role": "user", "content": enhanced_question},
                {"role": "assistant", "content": results.get("analysis") or ""},
            ]

        logger.info(
            "Question-driven analysis completed",
            symbol=symbol,
            iterations=results["iterations"],
            tools_used_count=len(results["tools_used"]),
        )

        return results

    async def validate(self, job: Job) -> bool:
        """Validate if this executor can handle the given job."""
        return job.execution_type in {
            INSTRUMENT_QUESTION_DRIVEN_TYPE,
            MARKET_QUESTION_DRIVEN_TYPE,
        }

    def get_executor_id(self) -> str:
        """Return the executor identifier."""
        return "question_driven_analysis"

    def _build_tool_descriptions(
        self, tools: list[Tool], symbol: str, current_date: str | None = None
    ) -> tuple[str, str]:
        """Build tool descriptions and examples for prompts.

        Args:
            tools: List of tools to describe
            symbol: Instrument symbol for example generation
            current_date: Today's date (YYYY-MM-DD). If None, computed from UTC now (no fallback).

        Returns:
            Tuple of (tools_description, tool_examples)
        """
        tool_descriptions = []
        tool_examples = []

        # Always use real current date for date examples (never hardcoded fallbacks)
        today = (
            datetime.now(UTC).date()
            if current_date is None
            else datetime.fromisoformat(current_date).date()
        )
        if current_date is None:
            current_date = today.isoformat()
        end_date_example = current_date
        start_date_example = (today - timedelta(days=365)).isoformat()

        for tool in tools:
            schema = tool.get_schema()
            params = schema.parameters.get("properties", {})
            required = schema.parameters.get("required", [])

            # Build parameter descriptions
            param_descs = []
            example_args: dict[str, Any] = {}
            for param_name, param_schema in params.items():
                param_type = param_schema.get("type", "")
                param_desc = param_schema.get("description", "")
                enum_vals = param_schema.get("enum", [])
                default_val = param_schema.get("default")

                param_info = f"{param_name} ({param_type})"
                if param_desc:
                    param_info += f": {param_desc}"
                if enum_vals:
                    param_info += f" [Options: {', '.join(enum_vals)}]"
                if default_val is not None:
                    param_info += f" [Default: {default_val}]"
                if param_name in required:
                    param_info += " [REQUIRED]"

                param_descs.append(f"    - {param_info}")

                # Build example args for required parameters (use current date for date params)
                if param_name in required:
                    if param_type == "string":
                        lowered_name = param_name.lower()
                        if "symbol" in lowered_name:
                            example_args[param_name] = symbol
                        elif param_name == "end_date":
                            example_args[param_name] = end_date_example
                        elif param_name == "start_date":
                            example_args[param_name] = start_date_example
                        elif "date" in lowered_name:
                            example_args[param_name] = end_date_example
                        else:
                            example_args[param_name] = "example"
                    elif param_type == "integer":
                        example_args[param_name] = 5

            tool_descriptions.append(
                f"  - {schema.name}: {schema.description}\n"
                f"    Parameters:\n" + "\n".join(param_descs)
            )

            # Build example tool call
            if example_args:
                tool_examples.append(
                    f'  {{"tool": "{schema.name}", "args": {json.dumps(example_args)}}}'
                )

        sec_routing = ""
        if any(t.get_name().startswith("get_sec_") for t in tools):
            sec_routing = (
                "SEC / EDGAR — pick the smallest tool that answers the question (do not default to listing filings):\n"
                "  • Multi-year or multi-period trends for ONE company → get_sec_company_facts_statement\n"
                "  • Compare headline metrics across TWO OR MORE tickers → get_sec_compare_financials_metrics\n"
                "  • Statement tables for ONE ticker (standardized recent bundle) → get_financial_statements\n"
                "  • Segment / dimensional rows or filing-native statement detail → get_sec_xbrl_statement_table\n"
                "  • Resolve CIK / SIC / entity identity → get_sec_company_edgar_profile\n"
                "  • ONLY filing index rows (dates, form, accession, URL) → get_sec_filings — not for revenue, EPS, or ratios\n"
                "  • Raw filing text/HTML after CIK + accession are known → get_sec_filing_content\n\n"
            )

        tools_description = sec_routing + "\n".join(tool_descriptions)
        examples_text = "\n".join(tool_examples) if tool_examples else ""

        return tools_description, examples_text
