"""LLM provider factory for creating providers from configuration."""

from typing import Any

import structlog

from copinanceos.infrastructure.analyzers.llm.config import LLMConfig
from copinanceos.infrastructure.analyzers.llm.providers.base import LLMProvider
from copinanceos.infrastructure.analyzers.llm.providers.gemini import GeminiProvider
from copinanceos.infrastructure.analyzers.llm.providers.ollama import OllamaProvider

logger = structlog.get_logger(__name__)


class LLMProviderFactory:
    """Factory for creating LLM providers from configuration."""

    @staticmethod
    def create_provider(
        provider_name: str,
        llm_config: LLMConfig | None = None,
        **override_kwargs: Any,
    ) -> LLMProvider:
        """Create an LLM provider from configuration.

        Args:
            provider_name: Name of the provider (e.g., "gemini", "ollama", "openai")
            llm_config: LLM configuration. If None, provider-specific defaults will be used.
            **override_kwargs: Override any configuration values

        Returns:
            LLMProvider instance

        Raises:
            ValueError: If provider_name is not supported
        """
        provider_name_lower = provider_name.lower()

        # Extract config values if provided
        api_key = override_kwargs.get("api_key")
        model_name = override_kwargs.get("model_name")
        base_url = override_kwargs.get("base_url")
        temperature = override_kwargs.get("temperature")
        max_output_tokens = override_kwargs.get("max_output_tokens")

        if llm_config:
            # Use config values if not overridden
            if api_key is None:
                api_key = llm_config.api_key
            if model_name is None:
                model_name = llm_config.model
            if base_url is None:
                base_url = llm_config.base_url
            if temperature is None:
                temperature = llm_config.temperature
            if max_output_tokens is None:
                max_output_tokens = llm_config.max_tokens

        if provider_name_lower == "gemini":
            return GeminiProvider(
                api_key=api_key,
                model_name=model_name or "gemini-1.5-pro",
                temperature=temperature or 0.7,
                max_output_tokens=max_output_tokens,
            )

        elif provider_name_lower == "ollama":
            return OllamaProvider(
                base_url=base_url or "http://localhost:11434",
                model_name=model_name or "llama2",
                temperature=temperature or 0.7,
                max_output_tokens=max_output_tokens,
            )

        # TODO: Add OpenAI and Anthropic providers when implemented
        elif provider_name_lower == "openai":
            raise ValueError(
                "OpenAI provider is not yet implemented. "
                "Please use 'gemini' or 'ollama' for now."
            )
        elif provider_name_lower == "anthropic":
            raise ValueError(
                "Anthropic provider is not yet implemented. "
                "Please use 'gemini' or 'ollama' for now."
            )

        else:
            raise ValueError(
                f"Unsupported LLM provider: {provider_name}. "
                f"Supported providers: gemini, ollama"
            )

    @staticmethod
    def get_provider_for_workflow(
        workflow_type: str,
        llm_config: LLMConfig | None = None,
        default_provider: str | None = None,
    ) -> str:
        """Get the provider name for a specific workflow.

        Args:
            workflow_type: The workflow type (e.g., "agent")
            llm_config: LLM configuration. If None, uses default_provider.
            default_provider: Default provider to use if no mapping is found

        Returns:
            Provider name to use for this workflow
        """
        if llm_config:
            return llm_config.get_provider_for_workflow(workflow_type)

        # Fall back to default provider
        if default_provider:
            return default_provider

        # Last resort: use "gemini" as default
        return "gemini"
