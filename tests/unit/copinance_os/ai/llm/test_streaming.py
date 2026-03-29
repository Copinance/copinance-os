"""Tests for LLM streaming contracts."""

import pytest
from pydantic import ValidationError

from copinance_os.ai.llm.streaming import LLMTextStreamEvent, normalize_text_streaming_mode


@pytest.mark.unit
def test_normalize_text_streaming_mode_invalid_defaults_to_auto() -> None:
    assert normalize_text_streaming_mode("not-a-mode") == "auto"
    assert normalize_text_streaming_mode(None) == "auto"
    assert normalize_text_streaming_mode("native") == "native"


@pytest.mark.unit
def test_llm_text_stream_event_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        LLMTextStreamEvent(  # type: ignore[call-arg]
            kind="done",
            native_streaming=False,
            extra_field=1,
        )
