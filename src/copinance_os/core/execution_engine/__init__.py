"""Analysis executors package."""

from copinance_os.core.execution_engine.backtest import execute_simple_long_only_backtest
from copinance_os.core.execution_engine.base import BaseAnalysisExecutor
from copinance_os.core.execution_engine.instrument_analysis import InstrumentAnalysisExecutor
from copinance_os.core.execution_engine.market_analysis import MarketAnalysisExecutor
from copinance_os.core.execution_engine.question_driven_analysis import (
    QuestionDrivenAnalysisExecutor,
)

__all__ = [
    "BaseAnalysisExecutor",
    "InstrumentAnalysisExecutor",
    "MarketAnalysisExecutor",
    "QuestionDrivenAnalysisExecutor",
    "execute_simple_long_only_backtest",
]
