"""LLM analyzer implementation using LLM providers.

This module implements the LLMAnalyzer interface using pluggable LLM providers.
The analyzer can work with any LLM provider that implements the LLMProvider interface.
"""

import structlog

from copinanceos.domain.ports.analyzers import LLMAnalyzer
from copinanceos.infrastructure.analyzers.llm.providers.base import LLMProvider
from copinanceos.infrastructure.analyzers.llm.providers.gemini import GeminiProvider
from copinanceos.infrastructure.analyzers.llm.resources.prompt_manager import PromptManager

logger = structlog.get_logger(__name__)


class LLMAnalyzerImpl(LLMAnalyzer):
    """Base implementation of LLMAnalyzer using an LLM provider.

    This class implements the LLMAnalyzer interface by delegating to an
    LLMProvider instance. This allows easy swapping of LLM backends.
    """

    def __init__(
        self,
        llm_provider: LLMProvider,
        prompt_manager: PromptManager | None = None,
    ) -> None:
        """Initialize LLM analyzer with a provider.

        Args:
            llm_provider: The LLM provider to use for text generation
            prompt_manager: Optional prompt manager. If None, creates default one.
        """
        self._llm_provider = llm_provider
        self._prompt_manager = prompt_manager or PromptManager()
        logger.info("Initialized LLM analyzer", provider=llm_provider.get_provider_name())


class GeminiLLMAnalyzer(LLMAnalyzerImpl):
    """Gemini-specific LLM analyzer convenience class.

    This is a convenience class for directly instantiating a Gemini-powered
    LLM analyzer. For framework-internal usage, use `LLMAnalyzerFactory` instead.

    Example:
        ```python
        from copinanceos.infrastructure.analyzers import GeminiLLMAnalyzer

        # Direct instantiation (convenience API)
        analyzer = GeminiLLMAnalyzer(api_key="your-key")

        # Or use factory (recommended for framework usage)
        from copinanceos.infrastructure.factories import LLMAnalyzerFactory
        analyzer = LLMAnalyzerFactory.create("gemini")
        ```

    Note:
        The framework internally uses `LLMAnalyzerFactory` which creates
        `LLMAnalyzerImpl` instances. This class is provided for convenience
        when you want to directly instantiate a Gemini analyzer without
        going through the factory.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-1.5-pro",
        temperature: float = 0.7,
        max_output_tokens: int | None = None,
    ) -> None:
        """Initialize Gemini LLM analyzer.

        Args:
            api_key: Gemini API key. Required for cloud usage.
            model_name: Gemini model to use (default: "gemini-1.5-pro")
                       Options: gemini-2.5-flash, gemini-1.5-pro, gemini-1.5-flash, gemini-pro
                       All support function calling for agentic workflows
            temperature: Default temperature for generation (0.0-1.0)
            max_output_tokens: Default max output tokens. If None, uses provider default.

        Note:
            For library integration, prefer using LLMAnalyzerFactory with LLMConfig instead
            of direct instantiation.
        """
        provider = GeminiProvider(
            api_key=api_key,
            model_name=model_name,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        super().__init__(provider)
