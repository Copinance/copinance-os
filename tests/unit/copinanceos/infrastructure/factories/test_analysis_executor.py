"""Unit tests for analysis executor factory."""

from unittest.mock import MagicMock, patch

import pytest

from copinanceos.infrastructure.analyzers.llm.config import LLMConfig
from copinanceos.infrastructure.factories.analysis_executor import AnalysisExecutorFactory


@pytest.mark.unit
class TestAnalysisExecutorFactory:
    """Test AnalysisExecutorFactory."""

    @pytest.fixture
    def mock_dependencies(self) -> dict:
        """Provide mock dependencies for analysis executor factory."""
        return {
            "get_instrument_use_case": MagicMock(),
            "get_quote_use_case": MagicMock(),
            "get_historical_data_use_case": MagicMock(),
            "get_options_chain_use_case": MagicMock(),
            "market_data_provider": MagicMock(),
            "macro_data_provider": MagicMock(),
            "fundamentals_use_case": MagicMock(),
            "fundamental_data_provider": MagicMock(),
            "sec_filings_provider": MagicMock(),
            "cache_manager": MagicMock(),
        }

    @patch("copinanceos.infrastructure.factories.analysis_executor.InstrumentAnalysisExecutor")
    def test_create_all_returns_static_executor(
        self, mock_market_executor: MagicMock, mock_dependencies: dict
    ) -> None:
        mock_executor = MagicMock()
        mock_market_executor.return_value = mock_executor
        result = AnalysisExecutorFactory.create_all(**mock_dependencies)
        assert len(result) >= 2
        assert mock_executor in result
        mock_market_executor.assert_called_once()

    @patch("copinanceos.infrastructure.factories.analysis_executor.LLMProviderFactory")
    @patch("copinanceos.infrastructure.factories.analysis_executor.LLMAnalyzerFactory")
    @patch("copinanceos.infrastructure.factories.analysis_executor.QuestionDrivenAnalysisExecutor")
    @patch("copinanceos.infrastructure.factories.analysis_executor.InstrumentAnalysisExecutor")
    def test_create_all_with_llm_analyzer(
        self,
        mock_market: MagicMock,
        mock_agentic: MagicMock,
        mock_llm_factory: MagicMock,
        mock_provider_factory: MagicMock,
        mock_dependencies: dict,
    ) -> None:
        llm_config = LLMConfig(provider="gemini", api_key="test-key")
        mock_provider_factory.get_provider_for_execution_type.return_value = "gemini"
        mock_llm_analyzer = MagicMock()
        mock_llm_analyzer._llm_provider = MagicMock()
        mock_llm_analyzer._llm_provider._api_key = "test_key"
        mock_llm_factory.create.return_value = mock_llm_analyzer
        mock_market_executor = MagicMock()
        mock_market.return_value = mock_market_executor
        mock_agentic_executor = MagicMock()
        mock_agentic.return_value = mock_agentic_executor
        result = AnalysisExecutorFactory.create_all(**mock_dependencies, llm_config=llm_config)
        assert len(result) == 3
        assert mock_market_executor in result
        assert mock_agentic_executor in result
        mock_agentic.assert_called_once()

    @patch("copinanceos.infrastructure.factories.analysis_executor.LLMProviderFactory")
    @patch("copinanceos.infrastructure.factories.analysis_executor.LLMAnalyzerFactory")
    @patch("copinanceos.infrastructure.factories.analysis_executor.QuestionDrivenAnalysisExecutor")
    @patch("copinanceos.infrastructure.factories.analysis_executor.InstrumentAnalysisExecutor")
    def test_create_all_without_api_key(
        self,
        mock_market: MagicMock,
        mock_agentic: MagicMock,
        mock_llm_factory: MagicMock,
        mock_provider_factory: MagicMock,
        mock_dependencies: dict,
    ) -> None:
        llm_config = LLMConfig(provider="gemini", api_key=None)
        mock_provider_factory.get_provider_for_execution_type.return_value = "gemini"
        mock_llm_analyzer = MagicMock()
        mock_llm_analyzer._llm_provider = MagicMock()
        mock_llm_analyzer._llm_provider._api_key = None
        mock_llm_factory.create.return_value = mock_llm_analyzer
        mock_market_executor = MagicMock()
        mock_market.return_value = mock_market_executor
        result = AnalysisExecutorFactory.create_all(**mock_dependencies, llm_config=llm_config)
        assert len(result) == 3
        assert mock_market_executor in result
        mock_agentic.assert_called_once()
        assert mock_agentic.call_args.kwargs.get("llm_analyzer") is None

    @patch("copinanceos.infrastructure.factories.analysis_executor.LLMProviderFactory")
    @patch("copinanceos.infrastructure.factories.analysis_executor.LLMAnalyzerFactory")
    @patch("copinanceos.infrastructure.factories.analysis_executor.InstrumentAnalysisExecutor")
    def test_create_all_handles_llm_factory_exception(
        self,
        mock_market: MagicMock,
        mock_llm_factory: MagicMock,
        mock_provider_factory: MagicMock,
        mock_dependencies: dict,
    ) -> None:
        llm_config = LLMConfig(provider="gemini", api_key="test-key")
        mock_provider_factory.get_provider_for_execution_type.side_effect = Exception(
            "Config error"
        )
        mock_market_executor = MagicMock()
        mock_market.return_value = mock_market_executor
        result = AnalysisExecutorFactory.create_all(**mock_dependencies, llm_config=llm_config)
        assert len(result) == 3
        assert mock_market_executor in result
