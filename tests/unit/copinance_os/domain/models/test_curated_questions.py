"""Unit tests for curated-questions domain models."""

import pytest

from copinance_os.domain.exceptions import ValidationError
from copinance_os.domain.models.curated_questions import (
    ArtifactType,
    filter_suggested_tools,
    validate_artifact_payload,
)


@pytest.mark.unit
def test_validate_sector_rotation_requires_sectors() -> None:
    with pytest.raises(ValidationError, match="sectors"):
        validate_artifact_payload(ArtifactType.SECTOR_ROTATION, {"sectors": []})


@pytest.mark.unit
def test_validate_quote_requires_symbol() -> None:
    with pytest.raises(ValidationError):
        validate_artifact_payload(ArtifactType.QUOTE, {"current_price": 100})


@pytest.mark.unit
def test_filter_suggested_tools_drops_unknown() -> None:
    allowed = frozenset({"get_market_quote", "get_options_chain"})
    assert filter_suggested_tools(
        ["get_market_quote", "bogus_tool"],
        allowed,
    ) == ["get_market_quote"]


@pytest.mark.unit
def test_filter_suggested_tools_none_passthrough() -> None:
    assert filter_suggested_tools(None, frozenset({"a"})) is None
