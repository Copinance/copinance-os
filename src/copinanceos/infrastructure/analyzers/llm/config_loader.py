"""Helper functions to load LLM configuration from environment variables.

This module provides backward compatibility for CLI and other entry points
that may want to read LLM configuration from environment variables.
Integrators should provide LLMConfig directly instead of using this module.
"""

import os
from typing import Any

from copinanceos.infrastructure.analyzers.llm.config import LLMConfig


def load_llm_config_from_env() -> LLMConfig | None:
    """Load LLM configuration from environment variables.

    This is a convenience function for CLI and backward compatibility.
    Integrators should provide LLMConfig directly instead of using this.

    Environment variables:
        COPINANCEOS_LLM_PROVIDER: Provider name (e.g., "gemini", "ollama")
        COPINANCEOS_GEMINI_API_KEY: Gemini API key
        COPINANCEOS_GEMINI_MODEL: Gemini model name
        COPINANCEOS_OPENAI_API_KEY: OpenAI API key
        COPINANCEOS_OPENAI_MODEL: OpenAI model name
        COPINANCEOS_OPENAI_BASE_URL: OpenAI base URL
        COPINANCEOS_ANTHROPIC_API_KEY: Anthropic API key
        COPINANCEOS_ANTHROPIC_MODEL: Anthropic model name
        COPINANCEOS_OLLAMA_BASE_URL: Ollama base URL
        COPINANCEOS_OLLAMA_MODEL: Ollama model name
        COPINANCEOS_LLM_TEMPERATURE: Temperature (default: 0.7)
        COPINANCEOS_LLM_MAX_TOKENS: Max tokens
        COPINANCEOS_WORKFLOW_LLM_PROVIDERS: Comma-separated workflow:provider mappings

    Returns:
        LLMConfig if any LLM-related environment variables are set, None otherwise
    """
    provider = os.getenv("COPINANCEOS_LLM_PROVIDER", "gemini")
    provider_lower = provider.lower()

    # Check if any LLM-related env vars are set
    has_llm_config = any(
        os.getenv(key) is not None
        for key in [
            "COPINANCEOS_LLM_PROVIDER",
            "COPINANCEOS_GEMINI_API_KEY",
            "COPINANCEOS_OPENAI_API_KEY",
            "COPINANCEOS_ANTHROPIC_API_KEY",
            "COPINANCEOS_OLLAMA_BASE_URL",
            "COPINANCEOS_OLLAMA_MODEL",
        ]
    )

    if not has_llm_config:
        return None

    # Extract provider-specific config
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None

    if provider_lower == "gemini":
        api_key = os.getenv("COPINANCEOS_GEMINI_API_KEY")
        model = os.getenv("COPINANCEOS_GEMINI_MODEL", "gemini-1.5-pro")
    elif provider_lower == "openai":
        api_key = os.getenv("COPINANCEOS_OPENAI_API_KEY")
        model = os.getenv("COPINANCEOS_OPENAI_MODEL", "gpt-4")
        base_url = os.getenv("COPINANCEOS_OPENAI_BASE_URL")
    elif provider_lower == "anthropic":
        api_key = os.getenv("COPINANCEOS_ANTHROPIC_API_KEY")
        model = os.getenv("COPINANCEOS_ANTHROPIC_MODEL", "claude-3-opus-20240229")
    elif provider_lower == "ollama":
        base_url = os.getenv("COPINANCEOS_OLLAMA_BASE_URL", "http://localhost:11434")
        model = os.getenv("COPINANCEOS_OLLAMA_MODEL", "llama2")

    # Parse workflow provider mapping
    workflow_providers: dict[str, str] = {}
    workflow_mapping_str = os.getenv("COPINANCEOS_WORKFLOW_LLM_PROVIDERS")
    if workflow_mapping_str:
        for pair in workflow_mapping_str.split(","):
            pair = pair.strip()
            if ":" in pair:
                workflow_type, provider_name = pair.split(":", 1)
                workflow_providers[workflow_type.strip()] = provider_name.strip()

    # Get temperature and max_tokens
    temperature_str = os.getenv("COPINANCEOS_LLM_TEMPERATURE", "0.7")
    try:
        temperature = float(temperature_str)
    except ValueError:
        temperature = 0.7

    max_tokens_str = os.getenv("COPINANCEOS_LLM_MAX_TOKENS")
    max_tokens: int | None = None
    if max_tokens_str:
        try:
            max_tokens = int(max_tokens_str)
        except ValueError:
            max_tokens = None

    # Build provider_config for any additional provider-specific settings
    provider_config: dict[str, Any] = {}
    if provider_lower == "openai" and base_url:
        provider_config["base_url"] = base_url

    return LLMConfig(
        provider=provider,
        api_key=api_key,
        model=model,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        workflow_providers=workflow_providers,
        provider_config=provider_config,
    )
