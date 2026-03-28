"""LLM policy strings are stable contracts for clients."""

from copinance_os.ai.llm.policy import NUMERIC_GROUNDING_POLICY


def test_numeric_grounding_policy_non_empty() -> None:
    assert "tool" in NUMERIC_GROUNDING_POLICY.lower()
    assert len(NUMERIC_GROUNDING_POLICY) > 40
