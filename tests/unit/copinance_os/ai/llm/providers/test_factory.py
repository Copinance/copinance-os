"""Unit tests for LLM provider factory."""

from unittest.mock import MagicMock, patch

import pytest

from copinance_os.ai.llm.config import LLMConfig
from copinance_os.ai.llm.providers.factory import LLMProviderFactory
from copinance_os.ai.llm.providers.gemini import GeminiProvider
from copinance_os.ai.llm.providers.ollama import OllamaProvider
from copinance_os.ai.llm.providers.openai import OpenAIProvider


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

    @patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True)
    @patch("copinance_os.ai.llm.providers.ollama.httpx")
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

    @patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True)
    @patch("copinance_os.ai.llm.providers.ollama.httpx")
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
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_client = MagicMock()
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
            llm_config = LLMConfig(provider="ollama", base_url="http://localhost:11434")
            provider = LLMProviderFactory.create_provider("OLLAMA", llm_config=llm_config)

            assert isinstance(provider, OllamaProvider)

    def test_create_provider_openai(self) -> None:
        """Test creating OpenAI provider."""
        llm_config = LLMConfig(provider="openai", api_key="sk-test")
        with (
            patch("copinance_os.ai.llm.providers.openai.OPENAI_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.openai.AsyncOpenAI") as mock_acls,
        ):
            mock_acls.return_value = MagicMock()
            provider = LLMProviderFactory.create_provider("openai", llm_config=llm_config)

        assert isinstance(provider, OpenAIProvider)
        assert provider._api_key == "sk-test"
        assert provider._model_name == "gpt-4o-mini"

    def test_create_provider_openai_with_overrides(self) -> None:
        """OpenAI provider respects config model and base_url."""
        llm_config = LLMConfig(
            provider="openai",
            api_key="sk-x",
            model="gpt-4o",
            base_url="https://example.invalid/v1",
        )
        with (
            patch("copinance_os.ai.llm.providers.openai.OPENAI_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.openai.AsyncOpenAI") as mock_acls,
        ):
            mock_acls.return_value = MagicMock()
            provider = LLMProviderFactory.create_provider("openai", llm_config=llm_config)

        assert provider._model_name == "gpt-4o"
        assert provider._base_url == "https://example.invalid/v1"

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

    def test_get_provider_for_execution_type_with_mapping(self) -> None:
        """Test getting provider for execution type with mapping configured."""
        llm_config = LLMConfig(
            provider="gemini",
            execution_type_providers={"stock": "ollama", "agent": "gemini"},
        )
        result = LLMProviderFactory.get_provider_for_execution_type("stock", llm_config=llm_config)

        assert result == "ollama"

    def test_get_provider_for_execution_type_without_mapping(self) -> None:
        """Test getting provider for execution type without mapping."""
        llm_config = LLMConfig(provider="gemini")
        result = LLMProviderFactory.get_provider_for_execution_type("stock", llm_config=llm_config)

        assert result == "gemini"

    def test_get_provider_for_execution_type_with_default_provider(self) -> None:
        """Test getting provider for execution type with default_provider parameter."""
        result = LLMProviderFactory.get_provider_for_execution_type(
            "stock", llm_config=None, default_provider="ollama"
        )

        assert result == "ollama"

    def test_get_provider_for_execution_type_default_overrides_config(self) -> None:
        """Test that default_provider parameter is used when llm_config is None."""
        # When llm_config is None, default_provider should be used
        result = LLMProviderFactory.get_provider_for_execution_type(
            "unknown_execution_type", llm_config=None, default_provider="ollama"
        )

        assert result == "ollama"

    def test_get_provider_for_execution_type_config_takes_precedence(self) -> None:
        """Test that llm_config provider is used when config is provided."""
        # When llm_config is provided, it takes precedence over default_provider
        llm_config = LLMConfig(provider="gemini")
        result = LLMProviderFactory.get_provider_for_execution_type(
            "unknown_execution_type", llm_config=llm_config, default_provider="ollama"
        )

        assert result == "gemini"  # Config provider takes precedence

    def test_get_provider_for_execution_type_uses_default_when_none(self) -> None:
        """Test that get_provider_for_execution_type uses default when llm_config is None."""
        result = LLMProviderFactory.get_provider_for_execution_type(
            "stock", llm_config=None, default_provider="gemini"
        )

        assert result == "gemini"

    def test_get_provider_for_execution_type_mapping_takes_precedence(self) -> None:
        """Test that execution type mapping takes precedence over default."""
        llm_config = LLMConfig(
            provider="gemini",
            execution_type_providers={"stock": "ollama"},
        )
        result = LLMProviderFactory.get_provider_for_execution_type(
            "stock", llm_config=llm_config, default_provider="gemini"
        )

        assert result == "ollama"
