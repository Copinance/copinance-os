"""AnthropicProvider: basic surface (construction, generate_text, availability,
provider identity) — not the tool-calling loop, see test_anthropic_tool_calling.py."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from copinance_os.ai.llm.providers.anthropic import AnthropicProvider


def _text_response(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )


def test_provider_name_is_anthropic() -> None:
    provider = AnthropicProvider(api_key="test-key")
    assert provider.get_provider_name() == "anthropic"


def test_model_name_defaults_to_claude_opus_5() -> None:
    provider = AnthropicProvider(api_key="test-key")
    assert provider.get_model_name() == "claude-opus-5"


def test_model_name_is_configurable() -> None:
    provider = AnthropicProvider(api_key="test-key", model_name="claude-sonnet-5")
    assert provider.get_model_name() == "claude-sonnet-5"


def test_supports_native_text_stream_is_false() -> None:
    """Disclosed scope cut — see anthropic.py's module docstring. False routes
    generate_text_stream to the base class's buffered fallback instead of
    raising or (worse) claiming incremental streaming that isn't implemented."""
    provider = AnthropicProvider(api_key="test-key")
    assert provider.supports_native_text_stream() is False


@pytest.mark.asyncio
async def test_is_available_false_without_api_key() -> None:
    provider = AnthropicProvider(api_key=None)
    assert await provider.is_available() is False


@pytest.mark.asyncio
async def test_generate_text_raises_when_client_not_initialized() -> None:
    provider = AnthropicProvider(api_key=None)
    with pytest.raises(RuntimeError):
        await provider.generate_text("test")


@pytest.mark.asyncio
async def test_generate_text_extracts_text_blocks() -> None:
    provider = AnthropicProvider(api_key="test-key")

    captured: dict[str, Any] = {}

    async def _fake_create(**kwargs: Any) -> SimpleNamespace:
        captured.update(kwargs)
        return _text_response("Hello from Claude.")

    provider._client = SimpleNamespace(messages=SimpleNamespace(create=_fake_create))

    result = await provider.generate_text("hi", system_prompt="be nice")

    assert result == "Hello from Claude."
    assert captured["model"] == "claude-opus-5"
    assert captured["messages"] == [{"role": "user", "content": "hi"}]
    # System is a cache-eligible block list, not a bare string.
    assert captured["system"][0]["text"] == "be nice"
    assert captured["system"][0]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_generate_text_requires_max_tokens_and_defaults_it() -> None:
    """Unlike OpenAI/Gemini, Anthropic's Messages API requires max_tokens —
    there is no server-side default. The provider must always supply one."""
    provider = AnthropicProvider(api_key="test-key")
    captured: dict[str, Any] = {}

    async def _fake_create(**kwargs: Any) -> SimpleNamespace:
        captured.update(kwargs)
        return _text_response("ok")

    provider._client = SimpleNamespace(messages=SimpleNamespace(create=_fake_create))

    await provider.generate_text("hi")

    assert isinstance(captured["max_tokens"], int)
    assert captured["max_tokens"] > 0


@pytest.mark.asyncio
async def test_generate_text_never_sends_temperature() -> None:
    """Regression: temperature was previously merged into create_kwargs as a
    top-level Messages API param. Opus 5 / Sonnet 5 / Fable 5 — the models
    this provider targets — reject a top-level `temperature` with a 400, so
    every single call failed. There is no sampling-temperature equivalent to
    forward it as; it must simply never be sent."""
    provider = AnthropicProvider(api_key="test-key")
    captured: dict[str, Any] = {}

    async def _fake_create(**kwargs: Any) -> SimpleNamespace:
        captured.update(kwargs)
        return _text_response("ok")

    provider._client = SimpleNamespace(messages=SimpleNamespace(create=_fake_create))

    await provider.generate_text("hi", temperature=0.3)

    assert "temperature" not in captured


@pytest.mark.asyncio
async def test_generate_text_forwards_output_config_effort_via_kwargs() -> None:
    """The documented replacement dial for temperature: output_config.effort,
    passed through **kwargs untouched."""
    provider = AnthropicProvider(api_key="test-key")
    captured: dict[str, Any] = {}

    async def _fake_create(**kwargs: Any) -> SimpleNamespace:
        captured.update(kwargs)
        return _text_response("ok")

    provider._client = SimpleNamespace(messages=SimpleNamespace(create=_fake_create))

    await provider.generate_text("hi", output_config={"effort": "high"})

    assert captured["output_config"] == {"effort": "high"}
