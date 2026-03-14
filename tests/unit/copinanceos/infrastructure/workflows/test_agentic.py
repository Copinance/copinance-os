"""Unit tests for agent workflow executor."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from copinanceos.domain.models.job import Job, JobScope, JobTimeframe
from copinanceos.domain.models.market import MarketType
from copinanceos.domain.ports.analyzers import LLMAnalyzer
from copinanceos.infrastructure.workflows import AgenticWorkflowExecutor


@pytest.mark.unit
class TestAgenticWorkflowExecutor:
    """Test AgenticWorkflowExecutor."""

    def test_get_workflow_type(self) -> None:
        """Test that get_workflow_type returns 'agent'."""
        executor = AgenticWorkflowExecutor()
        assert executor.get_workflow_type() == "agent"

    def test_initialization_without_llm_analyzer(self) -> None:
        """Test that executor can be initialized without LLM analyzer."""
        executor = AgenticWorkflowExecutor()
        assert executor._llm_analyzer is None

    def test_initialization_with_llm_analyzer(self) -> None:
        """Test that executor can be initialized with LLM analyzer."""
        mock_llm = MagicMock(spec=LLMAnalyzer)
        executor = AgenticWorkflowExecutor(llm_analyzer=mock_llm)
        assert executor._llm_analyzer is mock_llm

    async def test_validate_returns_true_for_agentic_workflow(self) -> None:
        """Test that validate returns True for agent workflow type."""
        executor = AgenticWorkflowExecutor()
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="AAPL",
            timeframe=JobTimeframe.LONG_TERM,
            workflow_type="agent",
        )
        result = await executor.validate(job)
        assert result is True

    async def test_validate_returns_false_for_non_agentic_workflow(self) -> None:
        """Test that validate returns False for non-agent workflow types."""
        executor = AgenticWorkflowExecutor()
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="AAPL",
            timeframe=JobTimeframe.LONG_TERM,
            workflow_type="equity",
        )
        result = await executor.validate(job)
        assert result is False

    async def test_execute_without_llm_analyzer(self) -> None:
        """Test execute when LLM analyzer is not configured."""
        executor = AgenticWorkflowExecutor()
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="AAPL",
            timeframe=JobTimeframe.MID_TERM,
            workflow_type="agent",
        )
        context = {"context_key": "context_value"}

        results = await executor.execute(job, context)

        assert results["status"] == "failed"
        assert results["error"] == "LLM analyzer not configured"
        assert results["message"] == "LLM analyzer is required for agent workflows"

    async def test_execute_with_llm_analyzer(self) -> None:
        """Test execute when LLM analyzer is configured."""
        mock_llm = MagicMock(spec=LLMAnalyzer)
        mock_provider = MagicMock()
        mock_provider.get_provider_name = MagicMock(return_value="test_provider")
        mock_provider.get_model_name = MagicMock(return_value="test-model")
        mock_provider.generate_with_tools = AsyncMock(
            return_value={
                "text": "Test analysis",
                "tool_calls": [],
                "iterations": 1,
            }
        )
        # Mock the _llm_provider attribute
        mock_llm._llm_provider = mock_provider
        # Mock hasattr check for generate_with_tools
        type(mock_provider).generate_with_tools = MagicMock()

        # Create executor with mock data providers
        mock_market_provider = MagicMock()
        executor = AgenticWorkflowExecutor(
            llm_analyzer=mock_llm,
            market_data_provider=mock_market_provider,
        )
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="TSLA",
            timeframe=JobTimeframe.LONG_TERM,
            workflow_type="agent",
        )
        context = {"question": "What is the current price of TSLA?"}

        results = await executor.execute(job, context)

        assert results["workflow_type"] == "agent"
        assert results["instrument_symbol"] == "TSLA"
        assert results["timeframe"] == "long_term"
        assert results["analysis_type"] == "agent"
        assert results["status"] == "completed"
        assert results["llm_provider"] == "test_provider"
        assert results["llm_model"] == "test-model"
        assert "analysis" in results

    async def test_execute_with_different_timeframes(self) -> None:
        """Test execute with different timeframes."""
        executor = AgenticWorkflowExecutor()

        for timeframe in JobTimeframe:
            job = Job(
                scope=JobScope.INSTRUMENT,
                market_type=MarketType.EQUITY,
                instrument_symbol="GOOGL",
                timeframe=timeframe,
                workflow_type="agent",
            )
            results = await executor.execute(job, {})
            assert results["timeframe"] == timeframe.value
            assert results["instrument_symbol"] == "GOOGL"

    async def test_prompt_cache_hit_uses_cached_prompts(self) -> None:
        """When cache_manager returns a valid prompt entry, get_prompt is not called."""
        mock_llm = MagicMock(spec=LLMAnalyzer)
        mock_provider = MagicMock()
        mock_provider.get_provider_name = MagicMock(return_value="test_provider")
        mock_provider.get_model_name = MagicMock(return_value="test-model")
        mock_provider.generate_with_tools = AsyncMock(
            return_value={
                "text": "Cached run",
                "tool_calls": [],
                "iterations": 1,
            }
        )
        mock_llm._llm_provider = mock_provider
        type(mock_provider).generate_with_tools = MagicMock()

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(
            return_value=MagicMock(
                data={
                    "system_prompt": "Cached system prompt",
                    "user_prompt": "Cached user prompt",
                }
            )
        )

        mock_market_provider = MagicMock()
        mock_prompt_manager = MagicMock()

        executor = AgenticWorkflowExecutor(
            llm_analyzer=mock_llm,
            market_data_provider=mock_market_provider,
            cache_manager=mock_cache,
            prompt_manager=mock_prompt_manager,
        )
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="AAPL",
            timeframe=JobTimeframe.MID_TERM,
            workflow_type="agent",
        )
        context = {"question": "What is the price?"}

        results = await executor.execute(job, context)

        assert results["status"] == "completed"
        mock_cache.get.assert_called_once()
        mock_prompt_manager.get_prompt.assert_not_called()
        # LLM should receive cached prompts
        call_kw = mock_provider.generate_with_tools.call_args.kwargs
        assert call_kw["system_prompt"] == "Cached system prompt"
        assert call_kw["prompt"] == "Cached user prompt"

    async def test_prompt_cache_miss_calls_get_prompt_and_sets_cache(self) -> None:
        """On cache miss, get_prompt is called and cache is set."""
        mock_llm = MagicMock(spec=LLMAnalyzer)
        mock_provider = MagicMock()
        mock_provider.get_provider_name = MagicMock(return_value="test_provider")
        mock_provider.get_model_name = MagicMock(return_value="test-model")
        mock_provider.generate_with_tools = AsyncMock(
            return_value={
                "text": "Analysis",
                "tool_calls": [],
                "iterations": 1,
            }
        )
        mock_llm._llm_provider = mock_provider
        type(mock_provider).generate_with_tools = MagicMock()

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)

        mock_prompt_manager = MagicMock()
        mock_prompt_manager.get_prompt = MagicMock(
            return_value=("Rendered system prompt", "Rendered user prompt")
        )

        mock_market_provider = MagicMock()
        executor = AgenticWorkflowExecutor(
            llm_analyzer=mock_llm,
            market_data_provider=mock_market_provider,
            cache_manager=mock_cache,
            prompt_manager=mock_prompt_manager,
        )
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="MSFT",
            timeframe=JobTimeframe.MID_TERM,
            workflow_type="agent",
        )
        context = {"question": "What is the PE?"}

        results = await executor.execute(job, context)

        assert results["status"] == "completed"
        mock_cache.get.assert_called_once()
        mock_prompt_manager.get_prompt.assert_called_once()
        mock_cache.set.assert_called_once()
        set_args, set_kw = mock_cache.set.call_args
        assert set_args[0] == "agent_prompt"
        assert set_args[1] == {
            "system_prompt": "Rendered system prompt",
            "user_prompt": "Rendered user prompt",
        }
