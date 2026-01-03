"""Factory for creating LLM analyzers."""

from copinanceos.domain.ports.analyzers import LLMAnalyzer
from copinanceos.infrastructure.analyzers.llm.config import LLMConfig
from copinanceos.infrastructure.analyzers.llm.llm import LLMAnalyzerImpl
from copinanceos.infrastructure.analyzers.llm.providers.factory import LLMProviderFactory


class LLMAnalyzerFactory:
    """Factory for creating LLM analyzer instances.

    This factory creates provider-agnostic analyzer instances using the generic
    LLMAnalyzerImpl class. For direct instantiation of provider-specific analyzers,
    use convenience classes like GeminiLLMAnalyzer.
    """

    @staticmethod
    def create(
        provider_name: str | None = None, llm_config: LLMConfig | None = None
    ) -> LLMAnalyzer:
        """Create LLM analyzer for a specific provider.

        This method uses the generic LLMAnalyzerImpl class to maintain
        provider-agnostic behavior. For convenience classes like GeminiLLMAnalyzer,
        instantiate them directly.

        Args:
            provider_name: Name of the LLM provider. If None and llm_config is provided,
                          uses provider from llm_config. Otherwise defaults to "gemini".
            llm_config: LLM configuration. If None, provider-specific defaults will be used.

        Returns:
            LLM analyzer instance (LLMAnalyzerImpl wrapping the provider)

        Example:
            ```python
            # Framework usage (provider-agnostic)
            from copinanceos.infrastructure.analyzers.llm.config import LLMConfig

            config = LLMConfig(
                provider="gemini",
                api_key="your-api-key",
                model="gemini-1.5-pro"
            )
            analyzer = LLMAnalyzerFactory.create("gemini", llm_config=config)

            # Direct usage (convenience)
            from copinanceos.infrastructure.analyzers import GeminiLLMAnalyzer
            analyzer = GeminiLLMAnalyzer(api_key="...")
            ```
        """
        if provider_name is None:
            if llm_config:
                provider_name = llm_config.provider
            else:
                provider_name = "gemini"  # Default fallback

        provider = LLMProviderFactory.create_provider(provider_name, llm_config)
        return LLMAnalyzerImpl(provider)

    @staticmethod
    def create_for_workflow(workflow_type: str, llm_config: LLMConfig | None = None) -> LLMAnalyzer:
        """Create LLM analyzer for a specific workflow type.

        Args:
            workflow_type: Type of workflow (e.g., "static", "agentic")
            llm_config: LLM configuration. If None, defaults will be used.

        Returns:
            LLM analyzer instance configured for the workflow
        """
        if llm_config:
            provider_name = llm_config.get_provider_for_workflow(workflow_type)
        else:
            provider_name = "gemini"  # Default fallback

        return LLMAnalyzerFactory.create(provider_name, llm_config)
