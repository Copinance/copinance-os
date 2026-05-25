"""Unit tests for curated-questions context builders."""

import json

import pytest

from copinance_os.data.curated_questions.context import (
    build_context,
    build_options_chain_context,
    build_quote_context,
    build_sector_rotation_context,
)
from copinance_os.domain.models.curated_questions import ArtifactType


@pytest.mark.unit
def test_build_options_chain_context_summarizes_oi() -> None:
    payload = {
        "underlying_symbol": "SPY",
        "expiration_date": "2026-06-19",
        "underlying_price": "500",
        "calls": [
            {
                "side": "call",
                "strike": "500",
                "open_interest": 1000,
                "volume": 50,
                "implied_volatility": "0.2",
            }
        ],
        "puts": [
            {
                "side": "put",
                "strike": "495",
                "open_interest": 800,
                "volume": 40,
                "implied_volatility": "0.22",
            }
        ],
    }
    ctx = build_options_chain_context(payload)
    assert ctx["underlying_symbol"] == "SPY"
    assert ctx["total_open_interest"] == 1800
    assert ctx["put_call_open_interest_ratio"] == pytest.approx(0.8)
    assert len(ctx["top_oi_strikes"]) >= 1


@pytest.mark.unit
def test_build_quote_context_includes_symbol() -> None:
    ctx = build_quote_context({"symbol": "AAPL", "current_price": "150"})
    assert ctx["symbol"] == "AAPL"
    assert ctx["artifact"] == ArtifactType.QUOTE.value


@pytest.mark.unit
def test_build_sector_rotation_context_top_bottom() -> None:
    payload = {
        "sectors": [
            {"name": "Tech", "momentum": 0.05},
            {"name": "Energy", "momentum": -0.02},
            {"name": "Health", "momentum": 0.01},
        ]
    }
    ctx = build_sector_rotation_context(payload)
    assert ctx["sector_count"] == 3
    assert len(ctx["top_momentum"]) <= 5


@pytest.mark.unit
def test_build_context_caps_large_payload() -> None:
    sectors = [{"name": f"S{i}", "momentum": i * 0.01} for i in range(200)]
    summary = build_context(
        ArtifactType.SECTOR_ROTATION,
        {"sectors": sectors},
    )
    assert len(json.dumps(summary, default=str)) <= 6000
