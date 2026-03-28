"""Unit tests for LLM analyzer implementation."""

from unittest.mock import MagicMock, patch

import pytest

from copinance_os.ai.llm.llm_analyzer import GeminiLLMAnalyzer, LLMAnalyzerImpl
from copinance_os.ai.llm.providers.base import LLMProvider


@pytest.mark.unit
class TestLLMAnalyzerImpl:
    """Test LLMAnalyzerImpl class."""

    def test_initialization_with_provider(self) -> None:
        """Test initialization with LLM provider."""
        mock_provider = MagicMock(spec=LLMProvider)
        mock_provider.get_provider_name = MagicMock(return_value="test_provider")

        analyzer = LLMAnalyzerImpl(llm_provider=mock_provider)

        assert analyzer._llm_provider is mock_provider


@pytest.mark.unit
class TestGeminiLLMAnalyzer:
    """Test GeminiLLMAnalyzer class."""

    @patch("copinance_os.ai.llm.llm_analyzer.GeminiProvider")
    def test_initialization_with_defaults(self, mock_gemini_provider_class: MagicMock) -> None:
        """Test GeminiLLMAnalyzer initialization with default parameters."""
        mock_provider = MagicMock()
        mock_provider.get_provider_name = MagicMock(return_value="gemini")
        mock_gemini_provider_class.return_value = mock_provider

        analyzer = GeminiLLMAnalyzer()

        mock_gemini_provider_class.assert_called_once_with(
            api_key=None,
            model_name="gemini-1.5-pro",
            temperature=0.7,
            max_output_tokens=None,
        )
        assert analyzer._llm_provider is mock_provider

    @patch("copinance_os.ai.llm.llm_analyzer.GeminiProvider")
    def test_initialization_with_custom_parameters(
        self, mock_gemini_provider_class: MagicMock
    ) -> None:
        """Test GeminiLLMAnalyzer initialization with custom parameters."""
        mock_provider = MagicMock()
        mock_provider.get_provider_name = MagicMock(return_value="gemini")
        mock_gemini_provider_class.return_value = mock_provider

        analyzer = GeminiLLMAnalyzer(
            api_key="test-key",
            model_name="gemini-1.5-pro",
            temperature=0.5,
            max_output_tokens=1000,
        )

        mock_gemini_provider_class.assert_called_once_with(
            api_key="test-key",
            model_name="gemini-1.5-pro",
            temperature=0.5,
            max_output_tokens=1000,
        )
        assert analyzer._llm_provider is mock_provider
