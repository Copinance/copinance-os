"""Unit tests for LLM provider base interface expectations."""

import inspect
from abc import ABC
from typing import Any

import pytest

from copinance_os.ai.llm.providers.base import LLMProvider
from copinance_os.ai.llm.streaming import LLMTextStreamEvent


class MockLLMProvider(LLMProvider):
    """Mock implementation of LLMProvider for testing."""

    def __init__(self, provider_name: str = "mock") -> None:
        """Initialize mock provider."""
        self._provider_name = provider_name
        self._is_available = True
        self._generate_text_response = "mock response"

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate text using the mock LLM."""
        return self._generate_text_response

    async def is_available(self) -> bool:
        """Check if the mock provider is available."""
        return self._is_available

    def get_provider_name(self) -> str:
        """Get the name of the mock provider."""
        return self._provider_name


@pytest.mark.unit
class TestLLMProviderInterface:
    """Test LLM provider interface contract expectations."""

    def test_llm_provider_is_abstract(self) -> None:
        """Test that LLMProvider is an abstract class."""
        assert issubclass(LLMProvider, ABC)

        # Should not be able to instantiate directly
        with pytest.raises(TypeError):
            LLMProvider()  # type: ignore[abstract]

    def test_llm_provider_has_generate_text_method(self) -> None:
        """Test that LLMProvider requires generate_text method."""
        provider = MockLLMProvider()

        # Check method exists and is callable
        assert hasattr(provider, "generate_text")
        assert callable(provider.generate_text)

        # Check it's an async method
        assert inspect.iscoroutinefunction(provider.generate_text)

    def test_llm_provider_has_is_available_method(self) -> None:
        """Test that LLMProvider requires is_available method."""
        provider = MockLLMProvider()

        # Check method exists and is callable
        assert hasattr(provider, "is_available")
        assert callable(provider.is_available)

        # Check it's an async method
        assert inspect.iscoroutinefunction(provider.is_available)

    def test_llm_provider_has_get_provider_name_method(self) -> None:
        """Test that LLMProvider requires get_provider_name method."""
        provider = MockLLMProvider()

        # Check method exists and is callable
        assert hasattr(provider, "get_provider_name")
        assert callable(provider.get_provider_name)

        # Check it's not async (synchronous method)
        assert not inspect.iscoroutinefunction(provider.get_provider_name)

    @pytest.mark.asyncio
    async def test_generate_text_signature(self) -> None:
        """Test that generate_text has correct signature and behavior."""
        provider = MockLLMProvider()

        # Test with minimal arguments
        result = await provider.generate_text("test prompt")
        assert isinstance(result, str)
        assert result == "mock response"

        # Test with all arguments
        result = await provider.generate_text(
            prompt="test prompt",
            system_prompt="system prompt",
            temperature=0.5,
            max_tokens=100,
            extra_param="value",
        )
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_generate_text_returns_string(self) -> None:
        """Test that generate_text always returns a string."""
        provider = MockLLMProvider()

        result = await provider.generate_text("test")
        assert isinstance(result, str)
        assert len(result) >= 0  # Can be empty string

    @pytest.mark.asyncio
    async def test_is_available_returns_boolean(self) -> None:
        """Test that is_available returns a boolean."""
        provider = MockLLMProvider()

        result = await provider.is_available()
        assert isinstance(result, bool)

    def test_get_provider_name_returns_string(self) -> None:
        """Test that get_provider_name returns a string."""
        provider = MockLLMProvider(provider_name="test-provider")

        result = provider.get_provider_name()
        assert isinstance(result, str)
        assert result == "test-provider"

    @pytest.mark.asyncio
    async def test_generate_text_handles_system_prompt(self) -> None:
        """Test that generate_text can handle system_prompt parameter."""
        provider = MockLLMProvider()

        # Test with None system prompt
        result1 = await provider.generate_text("test", system_prompt=None)
        assert isinstance(result1, str)

        # Test with system prompt
        result2 = await provider.generate_text("test", system_prompt="system")
        assert isinstance(result2, str)

    @pytest.mark.asyncio
    async def test_generate_text_handles_temperature(self) -> None:
        """Test that generate_text accepts temperature parameter."""
        provider = MockLLMProvider()

        # Test different temperature values
        for temp in [0.0, 0.5, 0.7, 1.0]:
            result = await provider.generate_text("test", temperature=temp)
            assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_generate_text_handles_max_tokens(self) -> None:
        """Test that generate_text accepts max_tokens parameter."""
        provider = MockLLMProvider()

        # Test with None
        result1 = await provider.generate_text("test", max_tokens=None)
        assert isinstance(result1, str)

        # Test with value
        result2 = await provider.generate_text("test", max_tokens=100)
        assert isinstance(result2, str)

    @pytest.mark.asyncio
    async def test_generate_text_handles_kwargs(self) -> None:
        """Test that generate_text accepts additional kwargs."""
        provider = MockLLMProvider()

        result = await provider.generate_text(
            "test", extra_param1="value1", extra_param2=42, extra_param3=True
        )
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_generate_text_handles_empty_prompt(self) -> None:
        """Test that generate_text can handle empty prompt."""
        provider = MockLLMProvider()

        result = await provider.generate_text("")
        assert isinstance(result, str)

    def test_provider_name_is_consistent(self) -> None:
        """Test that get_provider_name returns consistent value."""
        provider = MockLLMProvider(provider_name="consistent-name")

        name1 = provider.get_provider_name()
        name2 = provider.get_provider_name()

        assert name1 == name2
        assert name1 == "consistent-name"

    @pytest.mark.asyncio
    async def test_is_available_consistency(self) -> None:
        """Test that is_available returns consistent results."""
        provider = MockLLMProvider()
        provider._is_available = True

        result1 = await provider.is_available()
        result2 = await provider.is_available()

        assert result1 == result2
        assert result1 is True

    @pytest.mark.asyncio
    async def test_generate_text_stream_buffered_mode(self) -> None:
        """Buffered streaming wraps generate_text."""
        provider = MockLLMProvider()
        provider._generate_text_response = "full answer"

        events: list[LLMTextStreamEvent] = []
        async for ev in provider.generate_text_stream("q", stream_mode="buffered"):
            events.append(ev)

        assert [e.kind for e in events] == ["text_delta", "done"]
        assert events[0].text_delta == "full answer"
        assert events[0].native_streaming is False
        assert events[1].native_streaming is False

    @pytest.mark.asyncio
    async def test_generate_text_stream_native_unsupported_raises(self) -> None:
        """native mode raises when the provider has no native streaming."""
        provider = MockLLMProvider()

        events: list[LLMTextStreamEvent] = []
        with pytest.raises(RuntimeError, match="stream_mode=native not supported"):
            async for ev in provider.generate_text_stream("q", stream_mode="native"):
                events.append(ev)

        assert events == []

    @pytest.mark.asyncio
    async def test_generate_text_stream_error_event(self) -> None:
        """Errors surface as error events in buffered mode."""
        provider = MockLLMProvider()

        async def boom(*args: Any, **kwargs: Any) -> str:
            raise ValueError("fail")

        provider.generate_text = boom  # type: ignore[method-assign]

        events: list[LLMTextStreamEvent] = []
        async for ev in provider.generate_text_stream("q", stream_mode="buffered"):
            events.append(ev)

        assert len(events) == 1
        assert events[0].kind == "error"
        assert "fail" in (events[0].error_message or "")
