"""Integration guard: curated-question prompt tools exist in question-driven registry."""

import pytest

from copinance_os.ai.llm.resources import PromptManager
from copinance_os.core.pipeline.tools.discovery.allowlist import question_driven_tool_names


@pytest.mark.integration
def test_question_driven_tool_names_non_empty() -> None:
    names = question_driven_tool_names()
    assert "get_market_quote" in names
    assert "get_options_chain" in names


@pytest.mark.integration
def test_curated_questions_prompt_loads() -> None:
    pm = PromptManager()
    system, user = pm.get_prompt(
        "curated_questions",
        financial_literacy="intermediate",
        learning_step_line="",
        numeric_grounding_policy="test policy",
        allowed_tools="get_market_quote",
        artifact_type="quote",
        question_count="3",
        data_json="{}",
    )
    assert "get_market_quote" in system
    assert "quote" in user
