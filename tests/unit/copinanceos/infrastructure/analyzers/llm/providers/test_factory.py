"""Unit tests for LLM provider factory."""

from unittest.mock import MagicMock, patch

import pytest

from copinanceos.infrastructure.analyzers.llm.config import LLMConfig
from copinanceos.infrastructure.analyzers.llm.providers.factory import LLMProviderFactory
from copinanceos.infrastructure.analyzers.llm.providers.gemini import GeminiProvider
from copinanceos.infrastructure.analyzers.llm.providers.ollama import OllamaProvider


@pytest.mark.unit
class TestLLMProviderFactory:
    """Test LLMProviderFactory class."""

    def test_create_provider_gemini(self) -> None:
        """Test creating Gemini provider."""
        llm_config = LLMConfig(
            provider="gemini",
            api_key="test-key",
            model="gemini-pro",
        )
        provider = LLMProviderFactory.create_provider("gemini", llm_config=llm_config)

        assert isinstance(provider, GeminiProvider)
        assert provider._api_key == "test-key"
        assert provider._model_name == "gemini-pro"

    def test_create_provider_gemini_with_override_kwargs(self) -> None:
        """Test creating Gemini provider with override kwargs."""
        llm_config = LLMConfig(
            provider="gemini",
            api_key="default-key",
            model="default-model",
        )
        provider = LLMProviderFactory.create_provider(
            "gemini", llm_config=llm_config, api_key="override-key", model_name="override-model"
        )

        assert isinstance(provider, GeminiProvider)
        assert provider._api_key == "override-key"
        assert provider._model_name == "override-model"

    def test_create_provider_gemini_case_insensitive(self) -> None:
        """Test that provider name is case insensitive."""
        llm_config = LLMConfig(provider="gemini", api_key="test-key")
        provider = LLMProviderFactory.create_provider("GEMINI", llm_config=llm_config)

        assert isinstance(provider, GeminiProvider)

    @patch("copinanceos.infrastructure.analyzers.llm.providers.ollama.HTTPX_AVAILABLE", True)
    @patch("copinanceos.infrastructure.analyzers.llm.providers.ollama.httpx")
    def test_create_provider_ollama(self, mock_httpx: MagicMock) -> None:
        """Test creating Ollama provider."""
        mock_client = MagicMock()
        mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
        llm_config = LLMConfig(
            provider="ollama",
            base_url="http://custom:8080",
            model="mistral",
        )
        provider = LLMProviderFactory.create_provider("ollama", llm_config=llm_config)

        assert isinstance(provider, OllamaProvider)
        assert provider._base_url == "http://custom:8080"
        assert provider._model_name == "mistral"

    @patch("copinanceos.infrastructure.analyzers.llm.providers.ollama.HTTPX_AVAILABLE", True)
    @patch("copinanceos.infrastructure.analyzers.llm.providers.ollama.httpx")
    def test_create_provider_ollama_with_override_kwargs(self, mock_httpx: MagicMock) -> None:
        """Test creating Ollama provider with override kwargs."""
        mock_client = MagicMock()
        mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
        llm_config = LLMConfig(
            provider="ollama",
            base_url="http://default:11434",
            model="default-model",
        )
        provider = LLMProviderFactory.create_provider(
            "ollama",
            llm_config=llm_config,
            base_url="http://override:8080",
            model_name="override-model",
        )

        assert isinstance(provider, OllamaProvider)
        assert provider._base_url == "http://override:8080"
        assert provider._model_name == "override-model"

    def test_create_provider_ollama_case_insensitive(self) -> None:
        """Test that provider name is case insensitive."""
        with patch(
            "copinanceos.infrastructure.analyzers.llm.providers.ollama.HTTPX_AVAILABLE", True
        ):
            with patch(
                "copinanceos.infrastructure.analyzers.llm.providers.ollama.httpx"
            ) as mock_httpx:
                mock_client = MagicMock()
                mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
                llm_config = LLMConfig(provider="ollama", base_url="http://localhost:11434")
                provider = LLMProviderFactory.create_provider("OLLAMA", llm_config=llm_config)

                assert isinstance(provider, OllamaProvider)

    def test_create_provider_openai_raises_error(self) -> None:
        """Test that creating OpenAI provider raises ValueError."""
        llm_config = LLMConfig(provider="openai", api_key="test-key")
        with pytest.raises(ValueError, match="OpenAI provider is not yet implemented"):
            LLMProviderFactory.create_provider("openai", llm_config=llm_config)

    def test_create_provider_anthropic_raises_error(self) -> None:
        """Test that creating Anthropic provider raises ValueError."""
        llm_config = LLMConfig(provider="anthropic", api_key="test-key")
        with pytest.raises(ValueError, match="Anthropic provider is not yet implemented"):
            LLMProviderFactory.create_provider("anthropic", llm_config=llm_config)

    def test_create_provider_unsupported_raises_error(self) -> None:
        """Test that creating unsupported provider raises ValueError."""
        llm_config = LLMConfig(provider="unsupported", api_key="test-key")
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            LLMProviderFactory.create_provider("unsupported", llm_config=llm_config)

    def test_create_provider_uses_defaults_when_no_config(self) -> None:
        """Test that create_provider uses defaults when llm_config is None."""
        provider = LLMProviderFactory.create_provider("gemini", llm_config=None)

        assert isinstance(provider, GeminiProvider)
        # Should use default model when no config provided
        assert provider._model_name == "gemini-1.5-pro"

    def test_get_provider_for_workflow_with_mapping(self) -> None:
        """Test getting provider for workflow with mapping configured."""
        llm_config = LLMConfig(
            provider="gemini",
            workflow_providers={"static": "ollama", "agentic": "gemini"},
        )
        result = LLMProviderFactory.get_provider_for_workflow("static", llm_config=llm_config)

        assert result == "ollama"

    def test_get_provider_for_workflow_without_mapping(self) -> None:
        """Test getting provider for workflow without mapping."""
        llm_config = LLMConfig(provider="gemini")
        result = LLMProviderFactory.get_provider_for_workflow("static", llm_config=llm_config)

        assert result == "gemini"

    def test_get_provider_for_workflow_with_default_provider(self) -> None:
        """Test getting provider for workflow with default_provider parameter."""
        result = LLMProviderFactory.get_provider_for_workflow(
            "static", llm_config=None, default_provider="ollama"
        )

        assert result == "ollama"

    def test_get_provider_for_workflow_default_overrides_config(self) -> None:
        """Test that default_provider parameter is used when llm_config is None."""
        # When llm_config is None, default_provider should be used
        result = LLMProviderFactory.get_provider_for_workflow(
            "unknown_workflow", llm_config=None, default_provider="ollama"
        )

        assert result == "ollama"

    def test_get_provider_for_workflow_config_takes_precedence(self) -> None:
        """Test that llm_config provider is used when config is provided."""
        # When llm_config is provided, it takes precedence over default_provider
        llm_config = LLMConfig(provider="gemini")
        result = LLMProviderFactory.get_provider_for_workflow(
            "unknown_workflow", llm_config=llm_config, default_provider="ollama"
        )

        assert result == "gemini"  # Config provider takes precedence

    def test_get_provider_for_workflow_uses_default_when_none(self) -> None:
        """Test that get_provider_for_workflow uses default when llm_config is None."""
        result = LLMProviderFactory.get_provider_for_workflow(
            "static", llm_config=None, default_provider="gemini"
        )

        assert result == "gemini"

    def test_get_provider_for_workflow_mapping_takes_precedence(self) -> None:
        """Test that workflow mapping takes precedence over default."""
        llm_config = LLMConfig(
            provider="gemini",
            workflow_providers={"static": "ollama"},
        )
        result = LLMProviderFactory.get_provider_for_workflow(
            "static", llm_config=llm_config, default_provider="gemini"
        )

        assert result == "ollama"
