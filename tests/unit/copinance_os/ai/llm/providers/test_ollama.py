"""Unit tests for Ollama LLM provider."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from copinance_os.ai.llm.providers.base import LLMProvider
from copinance_os.ai.llm.providers.ollama import OllamaProvider


@pytest.mark.unit
class TestOllamaProvider:
    """Test Ollama provider implementation."""

    def test_ollama_provider_implements_llm_provider(self) -> None:
        """Test that OllamaProvider implements LLMProvider interface."""
        assert issubclass(OllamaProvider, LLMProvider)

    def test_ollama_provider_has_required_methods(self) -> None:
        """Test that OllamaProvider has all required methods."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_client = MagicMock()
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
            provider = OllamaProvider()

            assert hasattr(provider, "generate_text")
            assert hasattr(provider, "is_available")
            assert hasattr(provider, "get_provider_name")

            assert callable(provider.generate_text)
            assert callable(provider.is_available)
            assert callable(provider.get_provider_name)

    def test_get_provider_name_returns_ollama(self) -> None:
        """Test that get_provider_name returns 'ollama'."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_client = MagicMock()
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
            provider = OllamaProvider()

            name = provider.get_provider_name()
            assert name == "ollama"
            assert isinstance(name, str)

    def test_initialization_with_defaults(self) -> None:
        """Test provider initialization with default parameters."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_client = MagicMock()
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
            provider = OllamaProvider()

            assert provider._base_url == "http://localhost:11434"
            assert provider._model_name == "llama2"
            assert provider._default_temperature == 0.7
            assert provider._default_max_output_tokens is None
            assert provider._client is mock_client

    def test_initialization_with_custom_parameters(self) -> None:
        """Test provider initialization with custom parameters."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_client = MagicMock()
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
            provider = OllamaProvider(
                base_url="http://custom:8080",
                model_name="mistral",
                temperature=0.5,
                max_output_tokens=1000,
            )

            assert provider._base_url == "http://custom:8080"
            assert provider._model_name == "mistral"
            assert provider._default_temperature == 0.5
            assert provider._default_max_output_tokens == 1000

    def test_initialization_strips_trailing_slash_from_base_url(self) -> None:
        """Test that initialization strips trailing slash from base_url."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_client = MagicMock()
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
            provider = OllamaProvider(base_url="http://localhost:11434/")

            assert provider._base_url == "http://localhost:11434"

    def test_initialization_without_httpx(self) -> None:
        """Test that initialization handles missing httpx gracefully."""
        with patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", False):
            provider = OllamaProvider()

            assert provider._client is None

    def test_initialization_with_httpx_exception(self) -> None:
        """Test that initialization handles httpx client creation exception."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_httpx.AsyncClient = MagicMock(side_effect=Exception("Connection error"))
            provider = OllamaProvider()

            assert provider._client is None

    async def test_generate_text_success(self) -> None:
        """Test successful text generation."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value={"response": "Generated text"})
            mock_response.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            provider = OllamaProvider()
            result = await provider.generate_text("Test prompt")

            assert result == "Generated text"
            mock_client.post.assert_called_once()
            call_args = mock_client.post.call_args
            assert call_args[0][0] == "/api/generate"
            assert call_args[1]["json"]["model"] == "llama2"
            assert call_args[1]["json"]["prompt"] == "Test prompt"

    async def test_generate_text_with_system_prompt(self) -> None:
        """Test text generation with system prompt."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value={"response": "Response"})
            mock_response.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            provider = OllamaProvider()
            result = await provider.generate_text("User prompt", system_prompt="System prompt")

            assert result == "Response"
            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["prompt"] == "System prompt\n\nUser prompt"

    async def test_generate_text_with_custom_temperature(self) -> None:
        """Test text generation with custom temperature."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value={"response": "Response"})
            mock_response.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            provider = OllamaProvider()
            await provider.generate_text("Prompt", temperature=0.9)

            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["options"]["temperature"] == 0.9

    async def test_generate_text_with_default_temperature(self) -> None:
        """Test text generation uses default temperature when not provided."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value={"response": "Response"})
            mock_response.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            provider = OllamaProvider(temperature=0.5)
            await provider.generate_text("Prompt")

            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["options"]["temperature"] == 0.5

    async def test_generate_text_with_max_tokens(self) -> None:
        """Test text generation with max_tokens parameter."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value={"response": "Response"})
            mock_response.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            provider = OllamaProvider()
            await provider.generate_text("Prompt", max_tokens=500)

            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["options"]["num_predict"] == 500

    async def test_generate_text_with_default_max_tokens(self) -> None:
        """Test text generation uses default max_tokens when not provided."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value={"response": "Response"})
            mock_response.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            provider = OllamaProvider(max_output_tokens=1000)
            await provider.generate_text("Prompt")

            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["options"]["num_predict"] == 1000

    async def test_generate_text_with_additional_kwargs(self) -> None:
        """Test text generation with additional kwargs."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value={"response": "Response"})
            mock_response.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            provider = OllamaProvider()
            await provider.generate_text("Prompt", top_p=0.9, top_k=40)

            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["options"]["top_p"] == 0.9
            assert call_args[1]["json"]["options"]["top_k"] == 40

    async def test_generate_text_with_text_field_in_response(self) -> None:
        """Test text generation when response has 'text' field instead of 'response'."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value={"text": "Text response"})
            mock_response.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            provider = OllamaProvider()
            result = await provider.generate_text("Prompt")

            assert result == "Text response"

    async def test_generate_text_with_unexpected_response_format(self) -> None:
        """Test text generation with unexpected response format."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value={"unexpected": "format"})
            mock_response.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            provider = OllamaProvider()
            result = await provider.generate_text("Prompt")

            assert result == str({"unexpected": "format"})

    async def test_generate_text_raises_error_when_httpx_not_available(self) -> None:
        """Test that generate_text raises error when httpx is not available."""
        with patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", False):
            provider = OllamaProvider()

            with pytest.raises(RuntimeError, match="httpx package is not installed"):
                await provider.generate_text("Prompt")

    async def test_generate_text_raises_error_when_client_not_initialized(self) -> None:
        """Test that generate_text raises error when client is not initialized."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_httpx.AsyncClient = MagicMock(side_effect=Exception("Init error"))
            provider = OllamaProvider()

            with pytest.raises(RuntimeError, match="Ollama client is not initialized"):
                await provider.generate_text("Prompt")

    async def test_generate_text_handles_httpx_error(self) -> None:
        """Test that generate_text handles httpx HTTPError."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            # Create a mock HTTPError class
            class MockHTTPError(Exception):
                pass

            mock_http_error = MockHTTPError("HTTP 500")
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=mock_http_error)
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
            mock_httpx.HTTPError = MockHTTPError

            provider = OllamaProvider()

            with pytest.raises(RuntimeError, match="Ollama API call failed"):
                await provider.generate_text("Prompt")

    async def test_generate_text_handles_general_exception(self) -> None:
        """Test that generate_text re-raises general exceptions."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            # Create a non-HTTPError exception
            class MockOtherError(Exception):
                pass

            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=MockOtherError("General error"))
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)
            # Make sure HTTPError is a different class
            mock_httpx.HTTPError = type("HTTPError", (Exception,), {})

            provider = OllamaProvider()

            # General exceptions are re-raised
            with pytest.raises(MockOtherError, match="General error"):
                await provider.generate_text("Prompt")

    async def test_is_available_returns_false_when_httpx_not_available(self) -> None:
        """Test that is_available returns False when httpx is not available."""
        with patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", False):
            provider = OllamaProvider()
            result = await provider.is_available()
            assert result is False

    async def test_is_available_returns_false_when_client_not_initialized(self) -> None:
        """Test that is_available returns False when client is not initialized."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_httpx.AsyncClient = MagicMock(side_effect=Exception("Init error"))
            provider = OllamaProvider()
            result = await provider.is_available()
            assert result is False

    async def test_is_available_returns_true_when_ollama_accessible(self) -> None:
        """Test that is_available returns True when Ollama is accessible."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            provider = OllamaProvider()
            result = await provider.is_available()

            assert result is True
            mock_client.get.assert_called_once_with("/api/tags")

    async def test_is_available_returns_false_on_exception(self) -> None:
        """Test that is_available returns False when check fails."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection error"))
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            provider = OllamaProvider()
            result = await provider.is_available()

            assert result is False

    async def test_generate_text_stream_native_emits_ollama_chunks(self) -> None:
        """Streaming uses /api/generate with stream=true and NDJSON lines."""
        lines = [
            json.dumps({"response": "Hi ", "done": False}),
            json.dumps({"response": "there", "done": False}),
            json.dumps(
                {
                    "response": "",
                    "done": True,
                    "prompt_eval_count": 3,
                    "eval_count": 5,
                }
            ),
        ]

        async def mock_aiter_lines():
            for line in lines:
                yield line

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.aiter_lines = mock_aiter_lines

        class _StreamCM:
            async def __aenter__(self) -> MagicMock:
                return mock_response

            async def __aexit__(self, *args: object) -> None:
                return None

        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_client = MagicMock()
            mock_client.stream = MagicMock(return_value=_StreamCM())
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            provider = OllamaProvider()
            assert provider._client is mock_client

            deltas: list[str] = []
            kinds: list[str] = []
            usage = None
            async for ev in provider.generate_text_stream("ping", stream_mode="native"):
                kinds.append(ev.kind)
                if ev.kind == "text_delta":
                    deltas.append(ev.text_delta)
                if ev.kind == "done":
                    usage = ev.usage

            assert deltas == ["Hi ", "there"]
            assert kinds[-1] == "done"
            assert usage == {
                "input_tokens": 3,
                "output_tokens": 5,
                "total_tokens": 8,
            }
            mock_client.stream.assert_called_once()
            call_kw = mock_client.stream.call_args[1]
            assert call_kw["json"]["stream"] is True

    async def test_disable_native_forces_buffered_stream(self) -> None:
        """provider_config can disable native streaming (buffered only)."""
        with (
            patch("copinance_os.ai.llm.providers.ollama.HTTPX_AVAILABLE", True),
            patch("copinance_os.ai.llm.providers.ollama.httpx") as mock_httpx,
        ):
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.json = MagicMock(return_value={"response": "ok"})
            mock_response.raise_for_status = MagicMock()
            mock_response.status_code = 200
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_httpx.AsyncClient = MagicMock(return_value=mock_client)

            provider = OllamaProvider(disable_native_text_stream=True)
            assert provider.supports_native_text_stream() is False

            events = []
            async for ev in provider.generate_text_stream("x", stream_mode="auto"):
                events.append(ev)

            assert any(e.kind == "text_delta" and e.text_delta == "ok" for e in events)
            assert all(not e.native_streaming for e in events if e.kind != "error")
