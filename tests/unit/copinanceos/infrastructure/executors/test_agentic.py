"""Unit tests for question-driven analysis executor."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from copinanceos.application.use_cases.analyze import (
    INSTRUMENT_DETERMINISTIC_TYPE,
    INSTRUMENT_QUESTION_DRIVEN_TYPE,
)
from copinanceos.domain.models.job import Job, JobScope, JobTimeframe
from copinanceos.domain.models.market import MarketType
from copinanceos.domain.ports.analyzers import LLMAnalyzer
from copinanceos.infrastructure.analyzers.llm.resources import (
    ANALYZE_QUESTION_DRIVEN_PROMPT_NAME,
    PromptManager,
)
from copinanceos.infrastructure.executors import QuestionDrivenAnalysisExecutor


@pytest.mark.unit
class TestQuestionDrivenAnalysisExecutor:
    """Test QuestionDrivenAnalysisExecutor."""

    def test_get_executor_id(self) -> None:
        executor = QuestionDrivenAnalysisExecutor()
        assert executor.get_executor_id() == "question_driven_analysis"

    def test_initialization_without_llm_analyzer(self) -> None:
        """Test that executor can be initialized without LLM analyzer."""
        executor = QuestionDrivenAnalysisExecutor()
        assert executor._llm_analyzer is None

    def test_initialization_with_llm_analyzer(self) -> None:
        """Test that executor can be initialized with LLM analyzer."""
        mock_llm = MagicMock(spec=LLMAnalyzer)
        executor = QuestionDrivenAnalysisExecutor(llm_analyzer=mock_llm)
        assert executor._llm_analyzer is mock_llm

    async def test_validate_returns_true_for_question_driven_type(self) -> None:
        """Test that validate returns True for question-driven execution type."""
        executor = QuestionDrivenAnalysisExecutor()
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="AAPL",
            timeframe=JobTimeframe.LONG_TERM,
            execution_type=INSTRUMENT_QUESTION_DRIVEN_TYPE,
        )
        result = await executor.validate(job)
        assert result is True

    async def test_validate_returns_false_for_non_question_driven_type(self) -> None:
        """Test that validate returns False for non-question-driven execution types."""
        executor = QuestionDrivenAnalysisExecutor()
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="AAPL",
            timeframe=JobTimeframe.LONG_TERM,
            execution_type=INSTRUMENT_DETERMINISTIC_TYPE,
        )
        result = await executor.validate(job)
        assert result is False

    async def test_execute_without_llm_analyzer(self) -> None:
        """Test execute when LLM analyzer is not configured."""
        executor = QuestionDrivenAnalysisExecutor()
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="AAPL",
            timeframe=JobTimeframe.MID_TERM,
            execution_type=INSTRUMENT_QUESTION_DRIVEN_TYPE,
        )
        context = {"context_key": "context_value"}

        results = await executor.execute(job, context)

        assert results["status"] == "failed"
        assert results["error"] == "LLM analyzer not configured"
        assert results["message"] == "LLM analyzer is required for question-driven analysis"

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
        executor = QuestionDrivenAnalysisExecutor(
            llm_analyzer=mock_llm,
            market_data_provider=mock_market_provider,
        )
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="TSLA",
            timeframe=JobTimeframe.LONG_TERM,
            execution_type=INSTRUMENT_QUESTION_DRIVEN_TYPE,
        )
        context = {"question": "What is the current price of TSLA?"}

        results = await executor.execute(job, context)

        assert results["execution_type"] == "question_driven_analysis"
        assert results["instrument_symbol"] == "TSLA"
        assert results["timeframe"] == "long_term"
        assert results["execution_mode"] == "question_driven"
        assert results["status"] == "completed"
        assert results["llm_provider"] == "test_provider"
        assert results["llm_model"] == "test-model"
        assert "analysis" in results

    async def test_execute_with_different_timeframes(self) -> None:
        """Test execute with different timeframes."""
        executor = QuestionDrivenAnalysisExecutor()

        for timeframe in JobTimeframe:
            job = Job(
                scope=JobScope.INSTRUMENT,
                market_type=MarketType.EQUITY,
                instrument_symbol="GOOGL",
                timeframe=timeframe,
                execution_type=INSTRUMENT_QUESTION_DRIVEN_TYPE,
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

        executor = QuestionDrivenAnalysisExecutor(
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
            execution_type=INSTRUMENT_QUESTION_DRIVEN_TYPE,
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
        executor = QuestionDrivenAnalysisExecutor(
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
            execution_type=INSTRUMENT_QUESTION_DRIVEN_TYPE,
        )
        context = {"question": "What is the PE?"}

        results = await executor.execute(job, context)

        assert results["status"] == "completed"
        mock_cache.get.assert_called_once()
        mock_prompt_manager.get_prompt.assert_called_once()
        mock_cache.set.assert_called_once()
        set_args, set_kw = mock_cache.set.call_args
        assert set_args[0] == "question_analysis_prompt"
        assert set_args[1] == {
            "system_prompt": "Rendered system prompt",
            "user_prompt": "Rendered user prompt",
        }

    async def test_execute_uses_custom_prompt_templates_from_prompt_manager(self) -> None:
        """Executor with real PromptManager(templates=...) passes custom content to LLM."""
        custom_templates = {
            ANALYZE_QUESTION_DRIVEN_PROMPT_NAME: {
                "system_prompt": "Custom system. User level: {financial_literacy}.",
                "user_prompt": "Custom task: {question}",
            },
        }
        prompt_manager = PromptManager(templates=custom_templates)

        mock_llm = MagicMock(spec=LLMAnalyzer)
        mock_provider = MagicMock()
        mock_provider.get_provider_name = MagicMock(return_value="test_provider")
        mock_provider.get_model_name = MagicMock(return_value="test-model")
        mock_provider.generate_with_tools = AsyncMock(
            return_value={
                "text": "Done",
                "tool_calls": [],
                "iterations": 1,
            }
        )
        mock_llm._llm_provider = mock_provider
        type(mock_provider).generate_with_tools = MagicMock()

        mock_market_provider = MagicMock()
        executor = QuestionDrivenAnalysisExecutor(
            llm_analyzer=mock_llm,
            market_data_provider=mock_market_provider,
            cache_manager=None,
            prompt_manager=prompt_manager,
        )
        job = Job(
            scope=JobScope.INSTRUMENT,
            market_type=MarketType.EQUITY,
            instrument_symbol="MSFT",
            timeframe=JobTimeframe.MID_TERM,
            execution_type=INSTRUMENT_QUESTION_DRIVEN_TYPE,
        )
        # Include symbol in question so executor does not prepend "About equity instrument MSFT:"
        context = {"question": "What is the PE of MSFT?", "financial_literacy": "intermediate"}

        results = await executor.execute(job, context)

        assert results["status"] == "completed"
        call_kw = mock_provider.generate_with_tools.call_args.kwargs
        assert call_kw["system_prompt"] == "Custom system. User level: intermediate."
        assert call_kw["prompt"] == "Custom task: What is the PE of MSFT?"
