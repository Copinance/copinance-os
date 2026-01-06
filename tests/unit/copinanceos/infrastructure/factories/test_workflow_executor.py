"""Unit tests for workflow executor factory."""

from unittest.mock import MagicMock, patch

import pytest

from copinanceos.infrastructure.analyzers.llm.config import LLMConfig
from copinanceos.infrastructure.factories.workflow_executor import WorkflowExecutorFactory


@pytest.mark.unit
class TestWorkflowExecutorFactory:
    """Test WorkflowExecutorFactory."""

    @pytest.fixture
    def mock_dependencies(self) -> dict:
        """Provide mock dependencies for workflow executor factory."""
        return {
            "get_stock_use_case": MagicMock(),
            "market_data_provider": MagicMock(),
            "macro_data_provider": MagicMock(),
            "fundamentals_use_case": MagicMock(),
            "fundamental_data_provider": MagicMock(),
            "sec_filings_provider": MagicMock(),
            "cache_manager": MagicMock(),
        }

    @patch("copinanceos.infrastructure.factories.workflow_executor.StaticWorkflowExecutor")
    def test_create_all_returns_static_executor(
        self, mock_static_executor: MagicMock, mock_dependencies: dict
    ) -> None:
        """Test that create_all returns at least static executor (and other static executors)."""
        mock_executor = MagicMock()
        mock_static_executor.return_value = mock_executor

        result = WorkflowExecutorFactory.create_all(**mock_dependencies)

        assert len(result) >= 2
        assert mock_executor in result
        mock_static_executor.assert_called_once()

    @patch("copinanceos.infrastructure.factories.workflow_executor.LLMProviderFactory")
    @patch("copinanceos.infrastructure.factories.workflow_executor.LLMAnalyzerFactory")
    @patch("copinanceos.infrastructure.factories.workflow_executor.AgenticWorkflowExecutor")
    @patch("copinanceos.infrastructure.factories.workflow_executor.StaticWorkflowExecutor")
    def test_create_all_with_llm_analyzer(
        self,
        mock_static: MagicMock,
        mock_agentic: MagicMock,
        mock_llm_factory: MagicMock,
        mock_provider_factory: MagicMock,
        mock_dependencies: dict,
    ) -> None:
        """Test create_all when LLM analyzer is available."""
        # Setup mocks
        llm_config = LLMConfig(provider="gemini", api_key="test-key")
        mock_provider_factory.get_provider_for_workflow.return_value = "gemini"
        mock_llm_analyzer = MagicMock()
        mock_llm_analyzer._llm_provider = MagicMock()
        mock_llm_analyzer._llm_provider._api_key = "test_key"
        mock_llm_factory.create.return_value = mock_llm_analyzer
        mock_static_executor = MagicMock()
        mock_static.return_value = mock_static_executor
        mock_agentic_executor = MagicMock()
        mock_agentic.return_value = mock_agentic_executor

        result = WorkflowExecutorFactory.create_all(**mock_dependencies, llm_config=llm_config)

        assert len(result) == 3
        assert mock_static_executor in result
        assert mock_agentic_executor in result
        mock_agentic.assert_called_once()

    @patch("copinanceos.infrastructure.factories.workflow_executor.LLMProviderFactory")
    @patch("copinanceos.infrastructure.factories.workflow_executor.LLMAnalyzerFactory")
    @patch("copinanceos.infrastructure.factories.workflow_executor.AgenticWorkflowExecutor")
    @patch("copinanceos.infrastructure.factories.workflow_executor.StaticWorkflowExecutor")
    def test_create_all_without_api_key(
        self,
        mock_static: MagicMock,
        mock_agentic: MagicMock,
        mock_llm_factory: MagicMock,
        mock_provider_factory: MagicMock,
        mock_dependencies: dict,
    ) -> None:
        """Test create_all when LLM analyzer has no API key."""
        # Setup mocks
        llm_config = LLMConfig(provider="gemini", api_key=None)  # No API key
        mock_provider_factory.get_provider_for_workflow.return_value = "gemini"
        mock_llm_analyzer = MagicMock()
        mock_llm_analyzer._llm_provider = MagicMock()
        mock_llm_analyzer._llm_provider._api_key = None  # No API key
        mock_llm_factory.create.return_value = mock_llm_analyzer
        mock_static_executor = MagicMock()
        mock_static.return_value = mock_static_executor

        result = WorkflowExecutorFactory.create_all(**mock_dependencies, llm_config=llm_config)

        # Should only return static executor when API key is missing
        assert len(result) == 2
        assert mock_static_executor in result
        mock_agentic.assert_not_called()

    @patch("copinanceos.infrastructure.factories.workflow_executor.LLMProviderFactory")
    @patch("copinanceos.infrastructure.factories.workflow_executor.LLMAnalyzerFactory")
    @patch("copinanceos.infrastructure.factories.workflow_executor.StaticWorkflowExecutor")
    def test_create_all_handles_llm_factory_exception(
        self,
        mock_static: MagicMock,
        mock_llm_factory: MagicMock,
        mock_provider_factory: MagicMock,
        mock_dependencies: dict,
    ) -> None:
        """Test create_all handles exception when creating LLM analyzer."""
        # Setup mocks
        llm_config = LLMConfig(provider="gemini", api_key="test-key")
        mock_provider_factory.get_provider_for_workflow.side_effect = Exception("Config error")
        mock_static_executor = MagicMock()
        mock_static.return_value = mock_static_executor

        result = WorkflowExecutorFactory.create_all(**mock_dependencies, llm_config=llm_config)

        # Should still return static executor even if LLM creation fails
        assert len(result) == 2
        assert mock_static_executor in result
