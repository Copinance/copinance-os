"""LLM configuration model for integrators to provide LLM settings."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMConfig:
    """Configuration for LLM providers.

    This class is used by integrators to provide LLM configuration
    (API keys, provider, model, etc.) instead of reading from environment variables.

    Attributes:
        provider: LLM provider name (e.g., "gemini", "ollama", "openai", "anthropic")
        api_key: API key for the provider (required for cloud providers like Gemini, OpenAI, Anthropic)
        model: Model name to use (e.g., "gemini-1.5-pro", "gpt-4", "llama2")
        base_url: Base URL for the provider (optional, for custom endpoints or local providers like Ollama)
        temperature: Default temperature for generation (0.0 to 1.0)
        max_tokens: Default maximum tokens for generation
        workflow_providers: Optional mapping of workflow types to provider names
                          (e.g., {"agent": "gemini"})
        provider_config: Additional provider-specific configuration
    """

    provider: str
    api_key: str | None = None
    model: str | None = None
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    workflow_providers: dict[str, str] = field(default_factory=dict)
    provider_config: dict[str, Any] = field(default_factory=dict)

    def get_provider_for_workflow(self, workflow_type: str) -> str:
        """Get the provider name for a specific workflow type.

        Args:
            workflow_type: The workflow type (e.g., "agent")

        Returns:
            Provider name to use for this workflow
        """
        return self.workflow_providers.get(workflow_type, self.provider)
