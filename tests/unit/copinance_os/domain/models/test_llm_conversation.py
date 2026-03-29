"""Tests for LLM conversation helpers."""

import pytest

from copinance_os.domain.models.llm_conversation import (
    LLMConversationTurn,
    parse_conversation_history,
    validate_conversation_history_pairs,
)


@pytest.mark.unit
def test_validate_empty_history_ok() -> None:
    validate_conversation_history_pairs([])


@pytest.mark.unit
def test_validate_pairs_ok() -> None:
    validate_conversation_history_pairs(
        [
            LLMConversationTurn(role="user", content="hi"),
            LLMConversationTurn(role="assistant", content="hello"),
        ]
    )


@pytest.mark.unit
def test_validate_rejects_odd_length() -> None:
    with pytest.raises(ValueError, match="even length"):
        validate_conversation_history_pairs([LLMConversationTurn(role="user", content="a")])


@pytest.mark.unit
def test_validate_rejects_wrong_role_order() -> None:
    with pytest.raises(ValueError, match="index 0"):
        validate_conversation_history_pairs(
            [
                LLMConversationTurn(role="assistant", content="a"),
                LLMConversationTurn(role="user", content="b"),
            ]
        )


@pytest.mark.unit
def test_parse_coerces_dicts() -> None:
    turns = parse_conversation_history(
        [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}]
    )
    assert len(turns) == 2
    assert turns[0].role == "user"


@pytest.mark.unit
def test_parse_rejects_incomplete_pairs() -> None:
    with pytest.raises(ValueError, match="even length"):
        parse_conversation_history([{"role": "user", "content": "only"}])
