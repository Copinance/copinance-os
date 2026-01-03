"""Unit tests for LLM analyzer factory."""

from unittest.mock import MagicMock, patch

import pytest

from copinanceos.domain.ports.analyzers import LLMAnalyzer
from copinanceos.infrastructure.analyzers.llm.config import LLMConfig
from copinanceos.infrastructure.factories.llm_analyzer import LLMAnalyzerFactory


@pytest.mark.unit
class TestLLMAnalyzerFactory:
    """Test LLMAnalyzerFactory."""

    @patch("copinanceos.infrastructure.factories.llm_analyzer.LLMProviderFactory")
    @patch("copinanceos.infrastructure.factories.llm_analyzer.LLMAnalyzerImpl")
    def test_create_with_provider_name(
        self,
        mock_llm_impl: MagicMock,
        mock_factory: MagicMock,
    ) -> None:
        """Test create with explicit provider name."""
        mock_provider = MagicMock()
        mock_factory.create_provider.return_value = mock_provider
        mock_analyzer = MagicMock(spec=LLMAnalyzer)
        mock_llm_impl.return_value = mock_analyzer
        llm_config = LLMConfig(provider="gemini", api_key="test-key")

        result = LLMAnalyzerFactory.create(provider_name="gemini", llm_config=llm_config)

        assert result == mock_analyzer
        # create_provider is called with positional args: provider_name, llm_config
        mock_factory.create_provider.assert_called_once_with("gemini", llm_config)
        mock_llm_impl.assert_called_once_with(mock_provider)

    @patch("copinanceos.infrastructure.factories.llm_analyzer.LLMProviderFactory")
    @patch("copinanceos.infrastructure.factories.llm_analyzer.LLMAnalyzerImpl")
    def test_create_without_provider_name(
        self,
        mock_llm_impl: MagicMock,
        mock_factory: MagicMock,
    ) -> None:
        """Test create without provider name (uses default from config)."""
        llm_config = LLMConfig(provider="ollama", base_url="http://localhost:11434")
        mock_provider = MagicMock()
        mock_factory.create_provider.return_value = mock_provider
        mock_analyzer = MagicMock(spec=LLMAnalyzer)
        mock_llm_impl.return_value = mock_analyzer

        result = LLMAnalyzerFactory.create(provider_name=None, llm_config=llm_config)

        assert result == mock_analyzer
        # create_provider is called with positional args: provider_name, llm_config
        mock_factory.create_provider.assert_called_once_with("ollama", llm_config)
        mock_llm_impl.assert_called_once_with(mock_provider)

    @patch("copinanceos.infrastructure.factories.llm_analyzer.LLMProviderFactory")
    @patch("copinanceos.infrastructure.factories.llm_analyzer.LLMAnalyzerImpl")
    def test_create_for_workflow(
        self,
        mock_llm_impl: MagicMock,
        mock_factory: MagicMock,
    ) -> None:
        """Test create_for_workflow."""
        llm_config = LLMConfig(
            provider="gemini",
            api_key="test-key",
            workflow_providers={"agentic": "gemini"},
        )
        mock_provider = MagicMock()
        mock_factory.create_provider.return_value = mock_provider
        mock_analyzer = MagicMock(spec=LLMAnalyzer)
        mock_llm_impl.return_value = mock_analyzer

        result = LLMAnalyzerFactory.create_for_workflow("agentic", llm_config=llm_config)

        assert result == mock_analyzer
        # create_for_workflow calls llm_config.get_provider_for_workflow() directly,
        # which returns "gemini" from workflow_providers mapping
        # create_provider is called with positional args: provider_name, llm_config
        mock_factory.create_provider.assert_called_once_with("gemini", llm_config)
        mock_llm_impl.assert_called_once_with(mock_provider)
