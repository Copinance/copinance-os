"""Factory for creating LLM analyzers (kept separate from providers/ to avoid circular imports)."""

from copinance_os.ai.llm.config import LLMConfig
from copinance_os.ai.llm.llm_analyzer import LLMAnalyzerImpl
from copinance_os.ai.llm.providers.factory import LLMProviderFactory
from copinance_os.domain.ports.analyzers import LLMAnalyzer


class LLMAnalyzerFactory:
    """Factory for creating LLM analyzer instances.

    Creates provider-agnostic analyzer instances using the generic LLMAnalyzerImpl class.
    """

    @staticmethod
    def create(
        provider_name: str | None = None, llm_config: LLMConfig | None = None
    ) -> LLMAnalyzer:
        """Create LLM analyzer for a specific provider."""
        if provider_name is None:
            provider_name = llm_config.provider if llm_config else "gemini"
        provider = LLMProviderFactory.create_provider(provider_name, llm_config)
        return LLMAnalyzerImpl(provider)

    @staticmethod
    def create_for_execution_type(
        execution_type: str, llm_config: LLMConfig | None = None
    ) -> LLMAnalyzer:
        """Create LLM analyzer for an execution type (e.g. question_driven_analysis)."""
        if llm_config:
            provider_name = llm_config.get_provider_for_execution_type(execution_type)
        else:
            provider_name = "gemini"
        return LLMAnalyzerFactory.create(provider_name, llm_config)
