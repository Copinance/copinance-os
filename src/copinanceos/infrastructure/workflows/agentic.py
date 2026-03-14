"""Agentic workflow executor implementation."""

import json
from typing import Any

import structlog

from copinanceos.domain.models.job import Job, JobScope
from copinanceos.domain.models.market import MarketType
from copinanceos.domain.ports.analyzers import LLMAnalyzer
from copinanceos.domain.ports.data_providers import (
    FundamentalDataProvider,
    MacroeconomicDataProvider,
    MarketDataProvider,
)
from copinanceos.domain.ports.tools import Tool
from copinanceos.infrastructure.analyzers.llm.resources import PromptManager
from copinanceos.infrastructure.tools import (
    create_fundamental_data_tools,
    create_fundamental_data_tools_with_providers,
    create_macro_regime_indicators_tool,
    create_market_data_tools,
    create_rule_based_regime_tools,
)
from copinanceos.infrastructure.tools.analysis.market_regime.indicators import (
    create_market_regime_indicators_tool,
)
from copinanceos.infrastructure.workflows.base import BaseWorkflowExecutor

logger = structlog.get_logger(__name__)

# Cache key "tool name" for agent prompt cache (same CacheManager, different logical resource)
AGENT_PROMPT_CACHE_NAME = "agent_prompt"


class AgenticWorkflowExecutor(BaseWorkflowExecutor):
    """Executor for AI agent-based workflows.

    This executor uses LLM analyzers with tools to perform AI-powered analysis.
    The LLM can dynamically fetch data using tools and provide comprehensive answers.
    """

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
        """Initialize agent workflow executor.

        Args:
            llm_analyzer: Optional LLM analyzer. If None, executor will work without LLM.
            market_data_provider: Optional market data provider for tools.
            fundamental_data_provider: Optional fundamental data provider for tools.
            sec_filings_provider: Optional provider specifically for SEC filings (e.g., EDGAR).
                                 If provided, SEC filings tool will use this provider instead
                                 of fundamental_data_provider.
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

    async def _execute_workflow(self, job: Job, context: dict[str, Any]) -> dict[str, Any]:
        """
        Execute an agent workflow using LLM with tools.

        This executor uses LLM analyzers with data provider tools to perform
        dynamic AI-powered analysis. The LLM can fetch real-time data and
        provide comprehensive answers to questions about stocks.

        Args:
            job: The job to execute
            context: Execution context and parameters. Can include:
                - "question": Specific question to answer (optional)
                - "financial_literacy": User's financial literacy level (optional)

        Returns:
            Results dictionary containing workflow outputs including:
                - analysis: LLM's analysis text
                - tool_calls: Tools that were used
                - iterations: Number of LLM iterations
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
                "instrument_symbol is required for agent workflow when scope=instrument"
            )

        results: dict[str, Any] = {}

        # Check if LLM analyzer is available
        if self._llm_analyzer is None:
            results["status"] = "failed"
            results["error"] = "LLM analyzer not configured"
            results["message"] = "LLM analyzer is required for agent workflows"
            logger.warning("Agentic workflow executed without LLM analyzer")
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

        # Create tools from data providers
        tools: list = []
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
            indicators_tool = create_market_regime_indicators_tool(self._market_data_provider)
            tools.append(indicators_tool)

            # Add macro regime indicators tool (rates/credit/commodities) if configured
            if self._macro_data_provider:
                macro_tool = create_macro_regime_indicators_tool(
                    self._macro_data_provider, self._market_data_provider
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
            results["message"] = "At least one data provider is required for agent workflows"
            logger.warning("No tools available for agent workflow")
            return results

        # Validate that question is provided
        question = context.get("question")
        if not question:
            results["status"] = "failed"
            results["error"] = "Question is required"
            results["message"] = (
                f"A question is required for agent workflows. What is your question about {symbol}?"
            )
            logger.warning("Agentic workflow executed without question", symbol=symbol)
            return results

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

        # Build tool descriptions and examples
        tools_description, tool_examples = self._build_tool_descriptions(tools, symbol)

        # Get financial literacy level
        financial_literacy = context.get("financial_literacy", "intermediate")

        # Load prompts: use cache when available, otherwise render and cache
        cache_kw = {
            "prompt_name": "agentic_workflow",
            "question": enhanced_question,
            "tools_description": tools_description,
            "tool_examples": tool_examples,
            "financial_literacy": financial_literacy,
        }
        system_prompt = ""
        user_prompt = ""
        if self._cache_manager:
            entry = await self._cache_manager.get(AGENT_PROMPT_CACHE_NAME, **cache_kw)
            if entry and isinstance(entry.data, dict):
                system_prompt = entry.data.get("system_prompt", "") or ""
                user_prompt = entry.data.get("user_prompt", "") or ""
                if system_prompt and user_prompt:
                    logger.debug("Using cached prompts for agentic workflow", symbol=symbol)
        if not system_prompt or not user_prompt:
            system_prompt, user_prompt = self._prompt_manager.get_prompt(
                "agentic_workflow",
                question=enhanced_question,
                tools_description=tools_description,
                tool_examples=tool_examples,
                financial_literacy=financial_literacy,
            )
            if self._cache_manager:
                await self._cache_manager.set(
                    AGENT_PROMPT_CACHE_NAME,
                    {"system_prompt": system_prompt, "user_prompt": user_prompt},
                    **cache_kw,
                )

        logger.info(
            "Executing agentic workflow with tools",
            symbol=symbol,
            tool_count=len(tools),
            provider=llm_provider.get_provider_name(),
        )

        # Execute LLM with tools
        llm_result = await llm_provider.generate_with_tools(
            prompt=user_prompt,
            tools=tools,
            system_prompt=system_prompt,
            temperature=0.7,
            max_iterations=5,
        )

        # Extract results
        results["analysis"] = llm_result.get("text", "")
        results["tool_calls"] = llm_result.get("tool_calls", [])
        results["iterations"] = llm_result.get("iterations", 1)
        results["llm_provider"] = llm_provider.get_provider_name()
        results["llm_model"] = llm_provider.get_model_name()
        results["tools_used"] = [tc.get("tool") for tc in results["tool_calls"]]
        if context.get("include_prompt"):
            results["system_prompt"] = system_prompt
            results["user_prompt"] = user_prompt

        logger.info(
            "Agentic workflow completed",
            symbol=symbol,
            iterations=results["iterations"],
            tools_used_count=len(results["tools_used"]),
        )

        return results

    async def validate(self, job: Job) -> bool:
        """Validate if this executor can handle the given job."""
        return job.workflow_type == "agent"

    def get_workflow_type(self) -> str:
        """Get the workflow type identifier."""
        return "agent"

    def _build_tool_descriptions(self, tools: list[Tool], symbol: str) -> tuple[str, str]:
        """Build tool descriptions and examples for prompts.

        Args:
            tools: List of tools to describe
            symbol: Instrument symbol for example generation

        Returns:
            Tuple of (tools_description, tool_examples)
        """
        tool_descriptions = []
        tool_examples = []

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

                # Build example args for required parameters
                if param_name in required:
                    if param_type == "string":
                        lowered_name = param_name.lower()
                        if "symbol" in lowered_name:
                            example_args[param_name] = symbol
                        elif "date" in lowered_name:
                            example_args[param_name] = "2026-06-19"
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

        tools_description = "\n".join(tool_descriptions)
        examples_text = "\n".join(tool_examples) if tool_examples else ""

        return tools_description, examples_text
