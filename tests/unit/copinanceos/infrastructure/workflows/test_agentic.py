"""Unit tests for agentic workflow executor."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from copinanceos.domain.models.research import Research, ResearchTimeframe
from copinanceos.domain.ports.analyzers import LLMAnalyzer
from copinanceos.infrastructure.workflows import AgenticWorkflowExecutor


@pytest.mark.unit
class TestAgenticWorkflowExecutor:
    """Test AgenticWorkflowExecutor."""

    def test_get_workflow_type(self) -> None:
        """Test that get_workflow_type returns 'agentic'."""
        executor = AgenticWorkflowExecutor()
        assert executor.get_workflow_type() == "agentic"

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
        """Test that validate returns True for agentic workflow type."""
        executor = AgenticWorkflowExecutor()
        research = Research(
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.LONG_TERM,
            workflow_type="agentic",
        )
        result = await executor.validate(research)
        assert result is True

    async def test_validate_returns_false_for_non_agentic_workflow(self) -> None:
        """Test that validate returns False for non-agentic workflow types."""
        executor = AgenticWorkflowExecutor()
        research = Research(
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.LONG_TERM,
            workflow_type="static",
        )
        result = await executor.validate(research)
        assert result is False

    async def test_execute_without_llm_analyzer(self) -> None:
        """Test execute when LLM analyzer is not configured."""
        executor = AgenticWorkflowExecutor()
        research = Research(
            stock_symbol="AAPL",
            timeframe=ResearchTimeframe.MID_TERM,
            workflow_type="agentic",
        )
        context = {"context_key": "context_value"}

        results = await executor.execute(research, context)

        assert results["status"] == "failed"
        assert results["error"] == "LLM analyzer not configured"
        assert results["message"] == "LLM analyzer is required for agentic workflows"

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
        research = Research(
            stock_symbol="TSLA",
            timeframe=ResearchTimeframe.LONG_TERM,
            workflow_type="agentic",
        )
        context = {"question": "What is the current price of TSLA?"}

        results = await executor.execute(research, context)

        assert results["workflow_type"] == "agentic"
        assert results["stock_symbol"] == "TSLA"
        assert results["timeframe"] == "long_term"
        assert results["analysis_type"] == "agentic"
        assert results["status"] == "completed"
        assert results["llm_provider"] == "test_provider"
        assert results["llm_model"] == "test-model"
        assert "analysis" in results

    async def test_execute_with_different_timeframes(self) -> None:
        """Test execute with different timeframes."""
        executor = AgenticWorkflowExecutor()

        for timeframe in ResearchTimeframe:
            research = Research(
                stock_symbol="GOOGL",
                timeframe=timeframe,
                workflow_type="agentic",
            )
            results = await executor.execute(research, {})
            assert results["timeframe"] == timeframe.value
            assert results["stock_symbol"] == "GOOGL"
