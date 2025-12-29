"""Base LLM provider interface for extensibility.

This module provides a base interface for LLM providers, making it easy
to integrate different LLM services (Gemini, OpenAI, Anthropic, etc.).
"""

from abc import ABC, abstractmethod
from typing import Any

from copinanceos.domain.ports.tools import Tool


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
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate text using the LLM.

        Args:
            prompt: The user prompt/query
            system_prompt: Optional system prompt for context
            temperature: Sampling temperature (0.0 to 1.0)
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
            Provider name (e.g., "gemini", "openai", "anthropic")
        """
        pass

    def get_model_name(self) -> str | None:
        """Get the model name being used by this provider.

        Returns:
            Model name (e.g., "gemini-1.5-pro", "llama2") or None if not available
        """
        return None

    async def generate_with_tools(
        self,
        prompt: str,
        tools: list[Tool] | None = None,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        max_iterations: int = 5,
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
