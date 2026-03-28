"""LLM prompt resources.

This module provides prompt templates for LLM analysis tasks. Library clients
can inject their own templates via ``get_container(prompt_templates=...)`` or
``prompt_manager=PromptManager(templates=...)``; otherwise defaults are used.
"""

from copinance_os.ai.llm.resources.prompt_manager import (
    ANALYZE_QUESTION_DRIVEN_PROMPT_NAME,
    PromptManager,
)

__all__ = [
    "ANALYZE_QUESTION_DRIVEN_PROMPT_NAME",
    "PromptManager",
]
