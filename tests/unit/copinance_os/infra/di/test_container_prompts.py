"""Unit tests for container prompt template injection."""

import pytest

from copinance_os.ai.llm.resources import (
    ANALYZE_QUESTION_DRIVEN_PROMPT_NAME,
    PromptManager,
)
from copinance_os.infra.di import get_container, reset_container


@pytest.mark.unit
class TestContainerCustomPromptTemplates:
    """Validate that get_container() injects custom prompt templates correctly."""

    def teardown_method(self) -> None:
        """Reset global container after each test to avoid affecting other tests."""
        reset_container()

    def test_get_container_with_prompt_templates_injects_overlay(self) -> None:
        """Passing prompt_templates to get_container() uses overlay; resolved manager has templates."""
        reset_container()
        custom = {
            ANALYZE_QUESTION_DRIVEN_PROMPT_NAME: {
                "system_prompt": "Custom system",
                "user_prompt": "Custom user",
            },
        }
        container = get_container(
            prompt_templates=custom,
            load_from_env=False,
        )
        pm = container.prompt_manager()

        assert pm._templates.get(ANALYZE_QUESTION_DRIVEN_PROMPT_NAME) == {
            "system_prompt": "Custom system",
            "user_prompt": "Custom user",
        }
        system, user = pm.get_prompt(
            ANALYZE_QUESTION_DRIVEN_PROMPT_NAME,
            question="Q",
            tools_description="T",
            tool_examples="E",
            financial_literacy="intermediate",
        )
        assert system == "Custom system"
        assert user == "Custom user"

    def test_get_container_with_prompt_manager_uses_provided_instance(self) -> None:
        """Passing prompt_manager to get_container() uses that instance."""
        reset_container()
        my_pm = PromptManager(
            templates={
                ANALYZE_QUESTION_DRIVEN_PROMPT_NAME: {
                    "system_prompt": "My system",
                    "user_prompt": "My user",
                },
            }
        )
        container = get_container(
            prompt_manager=my_pm,
            load_from_env=False,
        )
        resolved = container.prompt_manager()

        assert resolved is my_pm
        system, user = resolved.get_prompt(
            ANALYZE_QUESTION_DRIVEN_PROMPT_NAME,
            question="Q",
            tools_description="T",
            tool_examples="E",
            financial_literacy="beginner",
        )
        assert system == "My system"
        assert user == "My user"

    def test_get_container_without_prompt_args_uses_default_manager(self) -> None:
        """When neither prompt_templates nor prompt_manager is passed, default PromptManager is used."""
        reset_container()
        container = get_container(load_from_env=False)
        pm = container.prompt_manager()

        assert isinstance(pm, PromptManager)
        assert pm._templates == {}
        # Default manager can still resolve analyze_question_driven from package
        system, user = pm.get_prompt(
            ANALYZE_QUESTION_DRIVEN_PROMPT_NAME,
            question="What is the price?",
            tools_description="...",
            tool_examples="...",
            financial_literacy="intermediate",
        )
        assert "financial" in system.lower() or "analyst" in system.lower()
        assert "What is the price?" in user
