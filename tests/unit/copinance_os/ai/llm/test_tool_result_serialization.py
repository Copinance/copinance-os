"""budget_tool_result / compact_json: the model-facing size budget applied to
tool results in every provider's tool-calling loop."""

from __future__ import annotations

import os

import pytest

from copinance_os.ai.llm.tool_result_serialization import (
    DEFAULT_MAX_RESULT_CHARS,
    ToonBlock,
    budget_tool_result,
    compact_json,
    compact_json_with_toon,
    per_call_max_chars,
)


@pytest.fixture
def toon_enabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("COPINANCEOS_TOON_TABULAR_ENABLED", "true")


def test_compact_json_has_no_indentation() -> None:
    assert compact_json({"a": 1, "b": [1, 2]}) == '{"a":1,"b":[1,2]}'


def test_small_payload_passes_through_unchanged() -> None:
    data = {"symbol": "AAPL", "price": 123.45}
    assert budget_tool_result(data) is data


def test_small_list_passes_through_unchanged() -> None:
    data = [{"date": f"2024-01-{i:02d}"} for i in range(5)]
    assert budget_tool_result(data) is data


def test_large_list_truncates_with_head_and_tail() -> None:
    data = [{"date": f"2024-{i:04d}", "value": i} for i in range(2000)]
    result = budget_tool_result(data, max_chars=1000)

    assert result["_truncated"] is True
    assert result["_total_items"] == 2000
    assert result["_omitted"] == 2000 - result["_items_shown"]
    # Head+tail, not just a head slice — the most recent entries survive too.
    assert result["data"][0] == data[0]
    assert result["data"][-1] == data[-1]


def test_large_dict_truncates_only_its_big_list_fields() -> None:
    data = {
        "underlying_symbol": "SPY",
        "calls": [{"strike": i} for i in range(500)],
        "puts": [{"strike": i} for i in range(500)],
    }
    result = budget_tool_result(data, max_chars=2000)

    assert result["underlying_symbol"] == "SPY"  # scalar fields untouched
    assert result["_truncated"] is True
    assert set(result["_truncated_fields"]) == {"calls", "puts"}
    assert result["_truncated_fields"]["calls"]["total_items"] == 500
    assert len(result["calls"]) < 500
    assert result["calls"][0] == data["calls"][0]
    assert result["calls"][-1] == data["calls"][-1]


def test_dict_with_small_list_fields_is_untouched_even_if_large() -> None:
    # A large payload whose bulk is scalar fields, not a truncatable list —
    # nothing to downsample, so it must pass through rather than error.
    data = {"blob": "x" * 5000}
    result = budget_tool_result(data, max_chars=1000)
    assert result is data


def test_default_budget_is_generous_but_finite() -> None:
    assert DEFAULT_MAX_RESULT_CHARS > 1000


def _uniform_rows(n: int) -> list[dict]:
    return [{"strike": i, "bid": i * 0.1, "ask": i * 0.1 + 0.05} for i in range(n)]


def test_toon_off_by_default_even_for_an_eligible_table() -> None:
    data = {"underlying_symbol": "SPY", "calls": _uniform_rows(20)}
    result = budget_tool_result(data, tool_name="get_options_chain")
    assert isinstance(result["calls"], list)


def test_toon_tabularizes_eligible_dict_field_when_enabled(toon_enabled) -> None:
    data = {"underlying_symbol": "SPY", "calls": _uniform_rows(20)}
    result = budget_tool_result(data, tool_name="get_options_chain")
    assert result["underlying_symbol"] == "SPY"
    assert isinstance(result["calls"], str)
    assert result["calls"].startswith("calls[20]{strike,bid,ask}:")


def test_toon_tabularizes_root_list_when_enabled(toon_enabled) -> None:
    data = _uniform_rows(20)
    result = budget_tool_result(data, tool_name="get_historical_market_data")
    assert isinstance(result, str)
    assert result.startswith("get_historical_market_data[20]{strike,bid,ask}:")


def test_toon_skips_denylisted_tool_even_when_enabled(toon_enabled) -> None:
    data = {"reference": _uniform_rows(20)}
    result = budget_tool_result(data, tool_name="get_market_quote")
    assert isinstance(result["reference"], list)


def test_toon_skips_small_or_narrow_tables_even_when_enabled(toon_enabled) -> None:
    too_few_rows = {"calls": [{"strike": 1, "bid": 1, "ask": 1}]}
    assert isinstance(
        budget_tool_result(too_few_rows, tool_name="get_options_chain")["calls"], list
    )

    too_few_columns = {"calls": [{"strike": i} for i in range(20)]}
    assert isinstance(
        budget_tool_result(too_few_columns, tool_name="get_options_chain")["calls"], list
    )


def test_toon_output_still_falls_under_truncation_when_still_oversized(toon_enabled) -> None:
    data = {"calls": _uniform_rows(5000)}
    result = budget_tool_result(data, tool_name="get_options_chain", max_chars=500)
    # Tabularized to a string, then that string is short enough on its own that
    # the dict-truncation branch (which only inspects list-valued fields) has
    # nothing left to truncate — this exercises the two stages composing safely
    # rather than double-processing the same field.
    assert isinstance(result["calls"], str)


# ---------------------------------------------------------------------------
# Regression: rows must truncate BEFORE encoding, and a TOON block must be
# spliced into the final message as raw text, never re-escaped inside JSON.
# Reported: on a 250-contract chain, TOON-on (23,681 chars, 250 escaped
# newlines) was *larger* than TOON-off (11,844 chars) instead of the expected
# ~72% reduction, because (a) a fully-encoded TOON string never matched the
# post-hoc list/dict truncation branches, so a huge table sailed straight
# through the budget, and (b) json.dumps-ing that string escaped every
# newline, more than offsetting TOON's own savings.
# ---------------------------------------------------------------------------


def _option_chain_rows(n: int) -> list[dict]:
    return [
        {
            "strike": 100 + i,
            "bid": round(5.0 - i * 0.01, 2),
            "ask": round(5.05 - i * 0.01, 2),
            "volume": 100 + i,
            "open_interest": 500 + i,
        }
        for i in range(n)
    ]


def test_toon_rows_are_truncated_before_encoding_not_after(toon_enabled) -> None:
    """A TOON block must be bounded by construction — nothing downstream can
    truncate a string the way it can a list."""
    data = {"calls": _option_chain_rows(5000)}
    result = budget_tool_result(data, tool_name="get_options_chain")
    block = result["calls"]
    assert isinstance(block, str)
    # Header declares the row count that was actually encoded, not 5000.
    row_count = int(block.split("[", 1)[1].split("]", 1)[0])
    assert row_count <= 80  # head=60 + tail=20 ceiling
    assert "omitted" in block


def test_toon_on_is_smaller_than_toon_off_for_a_large_chain() -> None:
    """The actual regression scenario: a 250-row chain must come out smaller
    with TOON on than off, not larger."""
    data = {"calls": _option_chain_rows(250)}

    off = budget_tool_result(dict(data), tool_name="get_options_chain")
    off_size = len(compact_json_with_toon(off))

    os.environ["COPINANCEOS_TOON_TABULAR_ENABLED"] = "true"
    try:
        on = budget_tool_result(dict(data), tool_name="get_options_chain")
    finally:
        del os.environ["COPINANCEOS_TOON_TABULAR_ENABLED"]
    on_size = len(compact_json_with_toon(on))

    assert on_size < off_size


def test_compact_json_with_toon_does_not_escape_the_block() -> None:
    obj = {"tool": "get_options_chain", "success": True, "data": ToonBlock("calls[1]{a}:\n  1")}
    rendered = compact_json_with_toon(obj)
    assert "\\n" not in rendered  # no escaped newline
    assert "calls[1]{a}:\n  1" in rendered  # real newline, spliced as raw text


def test_compact_json_with_toon_degrades_to_plain_compact_json_without_blocks() -> None:
    obj = {"a": 1, "b": [1, 2]}
    assert compact_json_with_toon(obj) == compact_json(obj)


def test_compact_json_with_toon_finds_a_block_nested_inside_a_list() -> None:
    obj = {"expirations": [{"data": ToonBlock("x[1]{a}:\n  1")}]}
    rendered = compact_json_with_toon(obj)
    assert "\\n" not in rendered
    assert "x[1]{a}:\n  1" in rendered


def test_toon_block_is_a_str_subclass_and_survives_plain_isinstance_checks() -> None:
    block = ToonBlock("x[1]{a}:\n  1")
    assert isinstance(block, str)


# ---------------------------------------------------------------------------
# per_call_max_chars: a per-turn budget, not per-call. Parallel execution
# means N tool calls in one turn can now return at once — a per-call constant
# applied independently to each lets the turn's total balloon to N x that
# constant, which is exactly backwards for a "budget."
# ---------------------------------------------------------------------------


def test_per_call_max_chars_single_call_gets_the_full_budget() -> None:
    assert per_call_max_chars(1) == DEFAULT_MAX_RESULT_CHARS
    assert per_call_max_chars(0) == DEFAULT_MAX_RESULT_CHARS


def test_per_call_max_chars_splits_evenly_across_a_batch() -> None:
    assert per_call_max_chars(4, total_budget=16_000) == 4_000


def test_per_call_max_chars_never_shrinks_below_the_floor() -> None:
    """A 50-call batch would otherwise get 320 chars each — truncated to the
    point of uselessness rather than merely compact."""
    assert per_call_max_chars(50, total_budget=16_000) == 2_000


def test_per_call_max_chars_batch_total_stays_near_the_turn_budget() -> None:
    n = 4
    total = per_call_max_chars(n) * n
    assert total <= DEFAULT_MAX_RESULT_CHARS * 1.1  # small floor-driven slack only
