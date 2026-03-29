"""Base LLM provider interface for extensibility.

This module provides a base interface for LLM providers, making it easy
to integrate different LLM services (Gemini, OpenAI, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

import structlog

from copinance_os.ai.llm.streaming import (
    LLMTextStreamEvent,
    TextStreamingMode,
    normalize_text_streaming_mode,
)
from copinance_os.domain.models.llm_conversation import LLMConversationTurn
from copinance_os.domain.ports.tools import Tool

logger = structlog.get_logger(__name__)


class LLMProvider(ABC):
    """Base interface for LLM providers.

    This abstract class defines the contract that all LLM providers must implement.
    By implementing this interface, users can easily swap between different LLM
    services without changing the analyzer code.
    """

    @abstractmethod
    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate text using the LLM.

        Args:
            prompt: The user prompt/query
            system_prompt: Optional system prompt for context
            temperature: Sampling temperature (0.0 to 1.0); ``None`` uses provider default
            max_tokens: Maximum tokens to generate
            **kwargs: Provider-specific additional parameters

        Returns:
            Generated text response

        Raises:
            Exception: If the LLM call fails
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the LLM provider is available and configured.

        Returns:
            True if the provider is available, False otherwise
        """
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get the name of the LLM provider.

        Returns:
            Provider name (e.g., "gemini", "openai")
        """
        pass

    def get_model_name(self) -> str | None:
        """Get the model name being used by this provider.

        Returns:
            Model name (e.g., "gemini-1.5-pro", "llama2") or None if not available
        """
        return None

    def supports_native_text_stream(self) -> bool:
        """Whether this provider can emit token chunks via API streaming.

        When False, ``stream_mode="auto"`` uses buffered fallback.
        """
        return False

    async def generate_text_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        *,
        stream_mode: TextStreamingMode | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[LLMTextStreamEvent, None]:
        """Generate text as a stream of :class:`LLMTextStreamEvent`.

        Buffered fallback calls :meth:`generate_text` once and emits a single
        ``text_delta`` plus ``done``. Native streaming is provider-specific.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            stream_mode: Override default mode (``auto`` / ``native`` / ``buffered``).
            **kwargs: Passed through to generation

        Yields:
            :class:`LLMTextStreamEvent` until ``done`` or ``error``.
        """
        if stream_mode is None:
            stream_mode = getattr(self, "_text_streaming_mode", "auto")
        mode = normalize_text_streaming_mode(stream_mode)
        wants_native = mode in ("auto", "native")
        native_supported = self.supports_native_text_stream()

        if mode == "buffered" or not wants_native:
            async for ev in self._generate_text_stream_buffered(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            ):
                yield ev
            return

        if mode == "native" and not native_supported:
            raise RuntimeError(
                f"stream_mode=native not supported for provider {self.get_provider_name()} "
                "(no native text streaming or disabled via configuration)."
            )

        if mode == "auto" and not native_supported:
            async for ev in self._generate_text_stream_buffered(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            ):
                yield ev
            return

        try:
            async for ev in self._iter_native_text_stream(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            ):
                yield ev
        except Exception as e:
            if mode == "native":
                logger.error(
                    "Native text stream failed",
                    provider=self.get_provider_name(),
                    error=str(e),
                )
                yield LLMTextStreamEvent(
                    kind="error",
                    native_streaming=True,
                    error_message=str(e),
                )
                return
            logger.warning(
                "Native text stream failed; falling back to buffered generate_text",
                provider=self.get_provider_name(),
                error=str(e),
            )
            async for ev in self._generate_text_stream_buffered(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            ):
                yield ev

    async def _generate_text_stream_buffered(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float | None,
        max_tokens: int | None,
        **kwargs: Any,
    ) -> AsyncGenerator[LLMTextStreamEvent, None]:
        try:
            text = await self.generate_text(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            if text:
                yield LLMTextStreamEvent(
                    kind="text_delta",
                    text_delta=text,
                    native_streaming=False,
                )
            yield LLMTextStreamEvent(kind="done", native_streaming=False)
        except Exception as e:
            yield LLMTextStreamEvent(
                kind="error",
                native_streaming=False,
                error_message=str(e),
            )

    async def _iter_native_text_stream(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float | None,
        max_tokens: int | None,
        **kwargs: Any,
    ) -> AsyncGenerator[LLMTextStreamEvent, None]:
        """Emit provider-native stream chunks. Subclasses override when applicable."""
        raise NotImplementedError(
            f"Native streaming not implemented for {self.get_provider_name()}"
        )
        # Unreachable; makes this an async generator for type checkers.
        yield LLMTextStreamEvent(kind="done", native_streaming=True)

    async def generate_with_tools(
        self,
        prompt: str,
        tools: list[Tool] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        max_iterations: int = 5,
        *,
        prior_conversation: list[LLMConversationTurn] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate text with optional tool usage.

        This method allows LLMs to use tools (function calling) during generation.
        If tools are provided, the LLM can decide to call them and the results
        will be fed back for continued generation.

        Args:
            prompt: The user prompt/query
            tools: Optional list of tools available to the LLM
            system_prompt: Optional system prompt for context
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            max_iterations: Maximum number of tool call iterations (to prevent loops)
            prior_conversation: Optional prior user/assistant turns; each provider maps
                this to its native chat/history API (not concatenated into ``prompt``).
            **kwargs: Provider-specific additional parameters

        Returns:
            Dictionary with:
                - "text": Final generated text
                - "tool_calls": List of tool calls made
                - "iterations": Number of iterations used

        Raises:
            NotImplementedError: If provider doesn't support tool calling
            Exception: If the LLM call fails

        Note:
            This is an optional method. Providers that don't support tools
            should raise NotImplementedError. The default implementation
            falls back to generate_text if no tools are provided.
        """
        if tools is None or len(tools) == 0:
            # Fallback to regular text generation if no tools
            text = await self.generate_text(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            return {
                "text": text,
                "tool_calls": [],
                "iterations": 1,
            }

        # If tools are provided but provider doesn't support them, raise error
        raise NotImplementedError(
            f"Tool calling not implemented for provider: {self.get_provider_name()}"
        )
