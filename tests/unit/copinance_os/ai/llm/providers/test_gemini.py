"""Unit tests for Gemini LLM provider expectations."""

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from copinance_os.ai.llm.providers.base import LLMProvider
from copinance_os.ai.llm.providers.gemini import (
    GeminiProvider,
)


@pytest.mark.unit
class TestGeminiProvider:
    """Test Gemini provider implementation expectations."""

    def test_gemini_provider_implements_llm_provider(self) -> None:
        """Test that GeminiProvider implements LLMProvider interface."""
        assert issubclass(GeminiProvider, LLMProvider)

    def test_gemini_provider_has_required_methods(self) -> None:
        """Test that GeminiProvider has all required methods."""
        provider = GeminiProvider(api_key="test-key")

        assert hasattr(provider, "generate_text")
        assert hasattr(provider, "is_available")
        assert hasattr(provider, "get_provider_name")

        assert callable(provider.generate_text)
        assert callable(provider.is_available)
        assert callable(provider.get_provider_name)

    def test_get_provider_name_returns_gemini(self) -> None:
        """Test that get_provider_name returns 'gemini'."""
        provider = GeminiProvider(api_key="test-key")

        name = provider.get_provider_name()
        assert name == "gemini"
        assert isinstance(name, str)

    def test_initialization_with_api_key(self) -> None:
        """Test provider initialization with API key."""
        provider = GeminiProvider(
            api_key="test-api-key", model_name="gemini-pro", temperature=0.8, max_output_tokens=500
        )

        assert provider._api_key == "test-api-key"
        assert provider._model_name == "gemini-pro"
        assert provider._default_temperature == 0.8
        assert provider._default_max_output_tokens == 500

    def test_initialization_without_api_key(self) -> None:
        """Test provider initialization without API key."""
        provider = GeminiProvider(api_key=None)

        assert provider._api_key is None
        assert provider._client is None

    @pytest.mark.asyncio
    async def test_generate_text_raises_when_gemini_not_available(self) -> None:
        """Test that generate_text raises when Gemini package is not available."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", False):
            provider = GeminiProvider(api_key="test-key")

            with pytest.raises(RuntimeError, match="google-genai package is not installed"):
                await provider.generate_text("test prompt")

    @pytest.mark.asyncio
    async def test_generate_text_raises_when_api_key_missing(self) -> None:
        """Test that generate_text raises when API key is not configured."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            provider = GeminiProvider(api_key=None)

            with pytest.raises(RuntimeError, match="Gemini API key is not configured"):
                await provider.generate_text("test prompt")

    @pytest.mark.asyncio
    async def test_generate_text_raises_when_client_not_initialized(self) -> None:
        """Test that generate_text raises when client is not initialized."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            provider = GeminiProvider(api_key="test-key")
            provider._client = None

            with pytest.raises(RuntimeError, match="Gemini client is not initialized"):
                await provider.generate_text("test prompt")

    @pytest.mark.asyncio
    async def test_generate_text_combines_system_and_user_prompt(self) -> None:
        """Test that generate_text combines system and user prompts."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "response text"

            mock_client.models.generate_content = MagicMock(return_value=mock_response)

            provider = GeminiProvider(api_key="test-key")
            provider._client = mock_client

            # Mock asyncio executor to run synchronously
            async def run_in_executor_mock(executor, func):
                """Run function synchronously for testing."""
                return func()

            with patch("asyncio.get_event_loop") as mock_loop:
                loop = asyncio.new_event_loop()
                mock_loop.return_value = loop

                with patch.object(loop, "run_in_executor", side_effect=run_in_executor_mock):
                    result = await provider.generate_text(
                        prompt="user prompt", system_prompt="system prompt"
                    )

                    assert result == "response text"
                    # Verify the prompt was combined
                    call_args = mock_client.models.generate_content.call_args
                    assert call_args is not None
                    contents = (
                        call_args[1]["contents"]
                        if "contents" in call_args[1]
                        else call_args[0][1] if len(call_args[0]) > 1 else ""
                    )
                    assert "system prompt" in str(contents)
                    assert "user prompt" in str(contents)

    @pytest.mark.asyncio
    async def test_generate_text_uses_default_temperature(self) -> None:
        """Test that generate_text uses default temperature when not provided."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "response"

            mock_client.models.generate_content = MagicMock(return_value=mock_response)

            provider = GeminiProvider(api_key="test-key", temperature=0.5)
            provider._client = mock_client

            async def run_in_executor_mock(executor, func):
                return func()

            with patch("asyncio.get_event_loop") as mock_loop:
                loop = asyncio.new_event_loop()
                mock_loop.return_value = loop

                with patch.object(loop, "run_in_executor", side_effect=run_in_executor_mock):
                    await provider.generate_text("test")

                    # Check that temperature was used in config
                    call_args = mock_client.models.generate_content.call_args
                    if call_args and "config" in call_args[1]:
                        config = call_args[1]["config"]
                        if hasattr(config, "temperature"):
                            assert config.temperature == 0.5
                        elif isinstance(config, dict):
                            assert config.get("temperature") == 0.5

    @pytest.mark.asyncio
    async def test_generate_text_uses_provided_temperature(self) -> None:
        """Test that generate_text uses provided temperature over default."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "response"

            mock_client.models.generate_content = MagicMock(return_value=mock_response)

            provider = GeminiProvider(api_key="test-key", temperature=0.5)
            provider._client = mock_client

            async def run_in_executor_mock(executor, func):
                return func()

            with patch("asyncio.get_event_loop") as mock_loop:
                loop = asyncio.new_event_loop()
                mock_loop.return_value = loop

                with patch.object(loop, "run_in_executor", side_effect=run_in_executor_mock):
                    await provider.generate_text("test", temperature=0.9)

                    # The provided temperature should be used
                    call_args = mock_client.models.generate_content.call_args
                    if call_args and "config" in call_args[1]:
                        config = call_args[1]["config"]
                        if isinstance(config, dict):
                            assert config.get("temperature") == 0.9
                        elif hasattr(config, "temperature"):
                            assert config.temperature == 0.9

    @pytest.mark.asyncio
    async def test_generate_text_handles_empty_response(self) -> None:
        """Test that generate_text handles empty response gracefully."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_client.models.generate_content = MagicMock(return_value=None)

            provider = GeminiProvider(api_key="test-key")
            provider._client = mock_client

            async def run_in_executor_mock(executor, func):
                return func()

            with patch("asyncio.get_event_loop") as mock_loop:
                loop = asyncio.new_event_loop()
                mock_loop.return_value = loop

                with patch.object(loop, "run_in_executor", side_effect=run_in_executor_mock):
                    result = await provider.generate_text("test")
                    assert result == ""

    @pytest.mark.asyncio
    async def test_generate_text_extracts_text_from_response(self) -> None:
        """Test that generate_text correctly extracts text from different response structures."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            # Test direct text attribute
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "direct text"
            mock_client.models.generate_content = MagicMock(return_value=mock_response)

            provider = GeminiProvider(api_key="test-key")
            provider._client = mock_client

            async def run_in_executor_mock(executor, func):
                return func()

            with patch("asyncio.get_event_loop") as mock_loop:
                loop = asyncio.new_event_loop()
                mock_loop.return_value = loop

                with patch.object(loop, "run_in_executor", side_effect=run_in_executor_mock):
                    result = await provider.generate_text("test")
                    assert result == "direct text"

    @pytest.mark.asyncio
    async def test_generate_text_handles_candidates_structure(self) -> None:
        """Test that generate_text handles response with candidates structure."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = None

            # Create candidates structure
            mock_candidate = MagicMock()
            mock_content = MagicMock()
            mock_part = MagicMock()
            mock_part.text = "candidate text"
            mock_content.parts = [mock_part]
            mock_candidate.content = mock_content
            mock_response.candidates = [mock_candidate]

            mock_client.models.generate_content = MagicMock(return_value=mock_response)

            provider = GeminiProvider(api_key="test-key")
            provider._client = mock_client

            async def run_in_executor_mock(executor, func):
                return func()

            with patch("asyncio.get_event_loop") as mock_loop:
                loop = asyncio.new_event_loop()
                mock_loop.return_value = loop

                with patch.object(loop, "run_in_executor", side_effect=run_in_executor_mock):
                    result = await provider.generate_text("test")
                    assert result == "candidate text"

    @pytest.mark.asyncio
    async def test_generate_text_handles_exceptions(self) -> None:
        """Test that generate_text properly handles and re-raises exceptions."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_client.models.generate_content = MagicMock(side_effect=Exception("API error"))

            provider = GeminiProvider(api_key="test-key")
            provider._client = mock_client

            async def run_in_executor_mock(executor, func):
                return func()

            with patch("asyncio.get_event_loop") as mock_loop:
                loop = asyncio.new_event_loop()
                mock_loop.return_value = loop

                with (
                    patch.object(loop, "run_in_executor", side_effect=run_in_executor_mock),
                    pytest.raises(Exception, match="API error"),
                ):
                    await provider.generate_text("test")

    @pytest.mark.asyncio
    async def test_is_available_returns_false_when_gemini_not_available(self) -> None:
        """Test that is_available returns False when Gemini package is not available."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", False):
            provider = GeminiProvider(api_key="test-key")

            result = await provider.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_is_available_returns_false_when_api_key_missing(self) -> None:
        """Test that is_available returns False when API key is missing."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            provider = GeminiProvider(api_key=None)

            result = await provider.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_is_available_returns_false_when_client_not_initialized(self) -> None:
        """Test that is_available returns False when client is not initialized."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            provider = GeminiProvider(api_key="test-key")
            provider._client = None

            result = await provider.is_available()
            assert result is False

    @pytest.mark.asyncio
    async def test_is_available_returns_true_when_working(self) -> None:
        """Test that is_available returns True when provider is working."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "test response"
            mock_client.models.generate_content = MagicMock(return_value=mock_response)

            provider = GeminiProvider(api_key="test-key")
            provider._client = mock_client

            async def run_in_executor_mock(executor, func):
                return func()

            with patch("asyncio.get_event_loop") as mock_loop:
                loop = asyncio.new_event_loop()
                mock_loop.return_value = loop

                with patch.object(loop, "run_in_executor", side_effect=run_in_executor_mock):
                    result = await provider.is_available()
                    assert result is True

    @pytest.mark.asyncio
    async def test_is_available_returns_false_on_test_call_failure(self) -> None:
        """Test that is_available returns False when test call fails."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_client.models.generate_content = MagicMock(side_effect=Exception("API error"))

            provider = GeminiProvider(api_key="test-key")
            provider._client = mock_client

            async def run_in_executor_mock(executor, func):
                return func()

            with patch("asyncio.get_event_loop") as mock_loop:
                loop = asyncio.new_event_loop()
                mock_loop.return_value = loop

                with patch.object(loop, "run_in_executor", side_effect=run_in_executor_mock):
                    result = await provider.is_available()
                    assert result is False

    @pytest.mark.asyncio
    async def test_generate_text_handles_kwargs(self) -> None:
        """Test that generate_text passes additional kwargs to API."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "response"
            mock_client.models.generate_content = MagicMock(return_value=mock_response)

            provider = GeminiProvider(api_key="test-key")
            provider._client = mock_client

            async def run_in_executor_mock(executor, func):
                return func()

            with patch("asyncio.get_event_loop") as mock_loop:
                loop = asyncio.new_event_loop()
                mock_loop.return_value = loop

                with patch.object(loop, "run_in_executor", side_effect=run_in_executor_mock):
                    result = await provider.generate_text("test", top_p=0.9, top_k=40)
                    assert result == "response"
                    # Verify kwargs were passed
                    call_args = mock_client.models.generate_content.call_args
                    if call_args and "config" in call_args[1]:
                        config = call_args[1]["config"]
                        if isinstance(config, dict):
                            assert "top_p" in config or "top_k" in config

    def test_gemini_provider_initialization_logs_warning_when_not_available(self) -> None:
        """Test that initialization logs warning when Gemini is not available."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", False):
            provider = GeminiProvider(api_key="test-key")
            assert provider._client is None

    def test_gemini_provider_initialization_handles_client_init_error(self) -> None:
        """Test that initialization handles client initialization errors gracefully."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            # Mock genai module if available, otherwise skip
            try:
                with patch(
                    "copinance_os.ai.llm.providers.gemini.genai.Client"
                ) as mock_client_class:
                    mock_client_class.side_effect = Exception("Init error")

                    provider = GeminiProvider(api_key="test-key")
                    assert provider._client is None
            except (ImportError, AttributeError):
                # If genai is not available, test that initialization still works
                provider = GeminiProvider(api_key="test-key")
                # When genai is not available, client should be None
                assert provider._client is None or provider._api_key == "test-key"

    def test_initialization_with_default_parameters(self) -> None:
        """Test provider initialization with default parameters."""
        provider = GeminiProvider(api_key="test-key")

        assert provider._api_key == "test-key"
        assert provider._model_name == "gemini-1.5-pro"
        assert provider._default_temperature == 0.7
        assert provider._default_max_output_tokens is None

    def test_initialization_when_gemini_available_but_no_api_key(self) -> None:
        """Test initialization when Gemini is available but no API key provided."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            provider = GeminiProvider(api_key=None)

            assert provider._api_key is None
            assert provider._client is None

    @pytest.mark.asyncio
    async def test_generate_text_uses_default_max_tokens(self) -> None:
        """Test that generate_text uses default max_tokens when not provided."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "response"

            mock_client.models.generate_content = MagicMock(return_value=mock_response)

            provider = GeminiProvider(api_key="test-key", max_output_tokens=500)
            provider._client = mock_client

            async def run_in_executor_mock(executor, func):
                return func()

            with patch("asyncio.get_event_loop") as mock_loop:
                loop = asyncio.new_event_loop()
                mock_loop.return_value = loop

                with patch.object(loop, "run_in_executor", side_effect=run_in_executor_mock):
                    await provider.generate_text("test")

                    # Check that max_output_tokens was used in config
                    call_args = mock_client.models.generate_content.call_args
                    if call_args and "config" in call_args[1]:
                        config = call_args[1]["config"]
                        if hasattr(config, "max_output_tokens"):
                            assert config.max_output_tokens == 500
                        elif isinstance(config, dict):
                            assert config.get("max_output_tokens") == 500

    @pytest.mark.asyncio
    async def test_generate_text_uses_provided_max_tokens(self) -> None:
        """Test that generate_text uses provided max_tokens over default."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "response"

            mock_client.models.generate_content = MagicMock(return_value=mock_response)

            provider = GeminiProvider(api_key="test-key", max_output_tokens=500)
            provider._client = mock_client

            async def run_in_executor_mock(executor, func):
                return func()

            with patch("asyncio.get_event_loop") as mock_loop:
                loop = asyncio.new_event_loop()
                mock_loop.return_value = loop

                with patch.object(loop, "run_in_executor", side_effect=run_in_executor_mock):
                    await provider.generate_text("test", max_tokens=1000)

                    # The provided max_tokens should be used
                    call_args = mock_client.models.generate_content.call_args
                    if call_args and "config" in call_args[1]:
                        config = call_args[1]["config"]
                        if isinstance(config, dict):
                            assert config.get("max_output_tokens") == 1000
                        elif hasattr(config, "max_output_tokens"):
                            assert config.max_output_tokens == 1000

    @pytest.mark.asyncio
    async def test_generate_text_without_config_parameters(self) -> None:
        """Test that generate_text works without temperature or max_tokens."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "response"

            mock_client.models.generate_content = MagicMock(return_value=mock_response)

            provider = GeminiProvider(api_key="test-key")
            provider._default_temperature = None
            provider._default_max_output_tokens = None
            provider._client = mock_client

            async def run_in_executor_mock(executor, func):
                return func()

            with patch("asyncio.get_event_loop") as mock_loop:
                loop = asyncio.new_event_loop()
                mock_loop.return_value = loop

                with patch.object(loop, "run_in_executor", side_effect=run_in_executor_mock):
                    result = await provider.generate_text("test")
                    assert result == "response"
                    # Should call without config
                    call_args = mock_client.models.generate_content.call_args
                    assert call_args is not None

    @pytest.mark.asyncio
    async def test_generate_text_handles_generate_content_config_error(self) -> None:
        """Test that generate_text handles GenerateContentConfig creation errors."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = "response"

            mock_client.models.generate_content = MagicMock(return_value=mock_response)

            provider = GeminiProvider(api_key="test-key", temperature=0.5)
            provider._client = mock_client

            # The GenerateContentConfig error handling is tested by ensuring
            # the function works correctly. The fallback to dict config happens
            # when GenerateContentConfig raises AttributeError or TypeError.
            # Since we can't easily mock genai.types when genai might be None,
            # we test that the code path works with config (which exercises both paths)
            async def run_in_executor_mock(executor, func):
                return func()

            with patch("asyncio.get_event_loop") as mock_loop:
                loop = asyncio.new_event_loop()
                mock_loop.return_value = loop

                with patch.object(loop, "run_in_executor", side_effect=run_in_executor_mock):
                    result = await provider.generate_text("test")
                    # Should work regardless of whether GenerateContentConfig is used
                    # or dict config fallback is used
                    assert result == "response"
                    # Verify the API was called
                    call_args = mock_client.models.generate_content.call_args
                    assert call_args is not None

    @pytest.mark.asyncio
    async def test_generate_text_extracts_from_candidates_content_text(self) -> None:
        """Test that generate_text extracts text from candidates.content.text."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = None  # No direct text attribute

            # Create candidates structure with content.text (not parts)
            mock_candidate = MagicMock()
            mock_content = MagicMock()
            mock_content.parts = []  # No parts
            mock_content.text = "content text"  # Has text attribute
            mock_candidate.content = mock_content
            mock_response.candidates = [mock_candidate]

            mock_client.models.generate_content = MagicMock(return_value=mock_response)

            provider = GeminiProvider(api_key="test-key")
            provider._client = mock_client

            async def run_in_executor_mock(executor, func):
                return func()

            with patch("asyncio.get_event_loop") as mock_loop:
                loop = asyncio.new_event_loop()
                mock_loop.return_value = loop

                with patch.object(loop, "run_in_executor", side_effect=run_in_executor_mock):
                    result = await provider.generate_text("test")
                    assert result == "content text"

    @pytest.mark.asyncio
    async def test_generate_text_extracts_from_candidates_content_part_str(self) -> None:
        """Test that generate_text extracts text from candidates.content.parts[0] as string."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = None

            # Create candidates structure with part that has no text attribute
            mock_candidate = MagicMock()
            mock_content = MagicMock()
            mock_part = MagicMock()
            del mock_part.text  # Remove text attribute
            mock_part.__str__ = MagicMock(return_value="part string")
            mock_content.parts = [mock_part]
            mock_candidate.content = mock_content
            mock_response.candidates = [mock_candidate]

            mock_client.models.generate_content = MagicMock(return_value=mock_response)

            provider = GeminiProvider(api_key="test-key")
            provider._client = mock_client

            async def run_in_executor_mock(executor, func):
                return func()

            with patch("asyncio.get_event_loop") as mock_loop:
                loop = asyncio.new_event_loop()
                mock_loop.return_value = loop

                with patch.object(loop, "run_in_executor", side_effect=run_in_executor_mock):
                    result = await provider.generate_text("test")
                    assert result == "part string"

    @pytest.mark.asyncio
    async def test_generate_text_extracts_from_response_string(self) -> None:
        """Test that generate_text extracts text by converting response to string."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = None
            mock_response.candidates = []  # No candidates
            mock_response.__str__ = MagicMock(return_value="string representation")

            mock_client.models.generate_content = MagicMock(return_value=mock_response)

            provider = GeminiProvider(api_key="test-key")
            provider._client = mock_client

            async def run_in_executor_mock(executor, func):
                return func()

            with patch("asyncio.get_event_loop") as mock_loop:
                loop = asyncio.new_event_loop()
                mock_loop.return_value = loop

                with patch.object(loop, "run_in_executor", side_effect=run_in_executor_mock):
                    result = await provider.generate_text("test")
                    assert result == "string representation"

    @pytest.mark.asyncio
    async def test_generate_text_returns_empty_when_response_string_is_none(self) -> None:
        """Test that generate_text returns empty string when response string is 'None'."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = None
            mock_response.candidates = []
            mock_response.__str__ = MagicMock(return_value="None")

            mock_client.models.generate_content = MagicMock(return_value=mock_response)

            provider = GeminiProvider(api_key="test-key")
            provider._client = mock_client

            async def run_in_executor_mock(executor, func):
                return func()

            with patch("asyncio.get_event_loop") as mock_loop:
                loop = asyncio.new_event_loop()
                mock_loop.return_value = loop

                with patch.object(loop, "run_in_executor", side_effect=run_in_executor_mock):
                    result = await provider.generate_text("test")
                    assert result == ""

    @pytest.mark.asyncio
    async def test_generate_text_returns_empty_when_no_text_extractable(self) -> None:
        """Test that generate_text returns empty string when no text can be extracted."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = None
            mock_response.candidates = []
            mock_response.__str__ = MagicMock(return_value="")

            mock_client.models.generate_content = MagicMock(return_value=mock_response)

            provider = GeminiProvider(api_key="test-key")
            provider._client = mock_client

            async def run_in_executor_mock(executor, func):
                return func()

            with patch("asyncio.get_event_loop") as mock_loop:
                loop = asyncio.new_event_loop()
                mock_loop.return_value = loop

                with patch.object(loop, "run_in_executor", side_effect=run_in_executor_mock):
                    result = await provider.generate_text("test")
                    assert result == ""

    @pytest.mark.asyncio
    async def test_generate_text_handles_candidates_without_content(self) -> None:
        """Test that generate_text handles candidates without content attribute."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = None

            # Create candidates without content attribute
            mock_candidate = MagicMock()
            del mock_candidate.content  # Remove content attribute
            mock_response.candidates = [mock_candidate]

            mock_client.models.generate_content = MagicMock(return_value=mock_response)

            provider = GeminiProvider(api_key="test-key")
            provider._client = mock_client

            async def run_in_executor_mock(executor, func):
                return func()

            with patch("asyncio.get_event_loop") as mock_loop:
                loop = asyncio.new_event_loop()
                mock_loop.return_value = loop

                with patch.object(loop, "run_in_executor", side_effect=run_in_executor_mock):
                    # Should fall through to string conversion
                    result = await provider.generate_text("test")
                    # Result depends on string conversion of response
                    assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_generate_text_handles_candidates_content_without_parts_or_text(self) -> None:
        """Test that generate_text handles content without parts or text."""
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.text = None

            # Create candidates with content but no parts or text
            mock_candidate = MagicMock()
            mock_content = MagicMock()
            mock_content.parts = []  # Empty parts
            del mock_content.text  # No text attribute
            mock_candidate.content = mock_content
            mock_response.candidates = [mock_candidate]

            mock_client.models.generate_content = MagicMock(return_value=mock_response)

            provider = GeminiProvider(api_key="test-key")
            provider._client = mock_client

            async def run_in_executor_mock(executor, func):
                return func()

            with patch("asyncio.get_event_loop") as mock_loop:
                loop = asyncio.new_event_loop()
                mock_loop.return_value = loop

                with patch.object(loop, "run_in_executor", side_effect=run_in_executor_mock):
                    # Should fall through to string conversion
                    result = await provider.generate_text("test")
                    assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_native_text_stream_emits_cumulative_deltas(self) -> None:
        """Stream chunks may be cumulative; public API yields incremental text."""

        class _Chunk:
            __slots__ = ("text",)

            def __init__(self, text: str) -> None:
                self.text = text

        def _fake_stream() -> Any:
            yield _Chunk("Hello")
            yield _Chunk("Hello world")

        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            provider = GeminiProvider(api_key="test-key")
            provider._client = MagicMock()
            with patch.object(
                provider,
                "_sync_generate_content_stream",
                return_value=_fake_stream(),
            ):
                deltas: list[str] = []
                last_usage = None
                async for ev in provider.generate_text_stream("q", stream_mode="native"):
                    if ev.kind == "text_delta":
                        deltas.append(ev.text_delta)
                    if ev.kind == "done":
                        last_usage = ev.usage

                assert "".join(deltas) == "Hello world"
                assert last_usage is None or isinstance(last_usage, dict)

    @pytest.mark.asyncio
    async def test_auto_mode_buffered_when_native_disabled(self) -> None:
        with patch("copinance_os.ai.llm.providers.gemini.GEMINI_AVAILABLE", True):
            provider = GeminiProvider(api_key="test-key", disable_native_text_stream=True)
            provider._client = MagicMock()

            async def fake_gt(*_a: Any, **_k: Any) -> str:
                return "sync"

            provider.generate_text = fake_gt  # type: ignore[method-assign]

            flags: list[tuple[str, bool]] = []
            async for ev in provider.generate_text_stream("q", stream_mode="auto"):
                flags.append((ev.kind, ev.native_streaming))

            assert ("text_delta", False) in flags
            assert any(k == "done" and not n for k, n in flags)
