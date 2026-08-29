"""Model-facing serialization for tool results: TOON/compact JSON with a real size budget.

Fixes defects shared by every provider's tool-calling loop (``openai.py``,
``gemini.py``, ``ollama.py``, ``anthropic.py``):

- ``json.dumps(..., indent=2)`` on every tool result sent back to the model.
  Indentation is pure overhead here — the model does not care about
  whitespace, only the token budget does.
- The existing 100-item truncation (``serialized_data[:100]``) was only ever
  applied to a *recorded* copy used for the returned/logged ``tool_calls_made``
  entry. The actual payload appended to the conversation as the tool result
  message used the raw, untruncated data. A single large options chain or XBRL
  statement table could consume the entire iteration budget on its own, and the
  truncation only ever fired for a bare top-level list — never for the large
  dict-shaped payloads (``get_options_chain``, ``get_sec_xbrl_statement_table``)
  that actually blow past reasonable size in practice.

**TOON tabularization** (default OFF — see ``toon_tabular_enabled``) applies
before compaction/truncation and, per the design doc's measurements, gets
further ahead than compaction alone (~72% vs ~32% token reduction on a
250-contract options chain) by declaring a uniform array's field names once
instead of repeating them per row. It is gated three ways, all deliberately
conservative until the Phase 4 eval A/B proves no accuracy regression per
provider:

1. ``COPINANCEOS_TOON_TABULAR_ENABLED`` env flag — off by default.
2. ``TOON_NEVER_TOOLS`` — an explicit denylist of tools whose result is a
   single nested object, not a table (``get_signal_study``,
   ``get_positioning_context``, ``get_market_regime_indicators``,
   ``get_macro_regime_indicators``, ``get_watchlist_context``,
   ``get_market_quote``), even if some sub-field of one of them happened to
   look tabular.
3. A structural eligibility gate (``_is_tabular_eligible``): only a list of
   >=8 uniform dict rows with >=3 columns tabularizes. Anything smaller, or
   non-uniform, stays plain JSON — TOON's own docs and independent
   benchmarking agree it can *lose* to JSON below that density.

Two correctness properties a TOON block depends on, both enforced here (an
earlier version of this module got both wrong — see the git history for
``_maybe_tabularize``/``budget_tool_result`` if you need the "before" shape):

- **Rows are truncated before encoding, not after.** Encoding first and then
  trying to truncate the result doesn't work — once a list becomes a TOON
  string, none of the list/dict truncation branches below match a plain
  ``str``, so an oversized table sailed straight through the budget entirely.
  ``_tabularize_rows`` bounds row count (head+tail, same policy as the
  fallback list truncation) *before* calling ``encode_toon_table``, so a TOON
  block is bounded by construction.
- **A TOON block is spliced into the message as raw text, never as a quoted
  JSON string value.** ``ToonBlock`` marks a string as "this came from
  ``encode_toon_table`` — do not escape it"; ``compact_json_with_toon`` is the
  only function that should ever serialize a structure that might contain
  one. Running a `ToonBlock`-bearing structure through plain ``compact_json``
  round-trips the table through ``json.dumps``, which escapes every newline
  as ``\\n`` and every embedded quote — the token savings evaporate (the
  escaped form is *longer* than compact JSON of the original rows) and the
  model receives one long quoted blob instead of a table it can read.
"""

from __future__ import annotations

import json
import os
from typing import Any

from copinance_os.ai.llm.toon_encoding import encode_toon_table

# ~4k tokens at a ~4-chars/token rule of thumb — generous headroom for a single
# tool result before it starts crowding out everything else in the budget.
# This is a PER-TURN ceiling (see per_call_max_chars) — it was applied
# per-call before ToolRuntime made parallel execution real, which was
# self-limiting only because calls ran one at a time. Once several calls in
# one turn can return at once, applying this same constant to each
# independently lets a turn's total balloon to (batch size) x this — the
# opposite of a budget.
DEFAULT_MAX_RESULT_CHARS = 16_000

# Never shrink a single call's share below this, however large the batch —
# a tool given a sliver of the turn budget (e.g. 16000/20 calls = 800 chars)
# would truncate to the point of uselessness rather than to the point of
# being merely compact.
_MIN_PER_CALL_CHARS = 2_000

_LIST_MIN_SIZE_TO_TRUNCATE = 20

_MIN_ROWS_FOR_TABULAR = 8
_MIN_COLUMNS_FOR_TABULAR = 3

# How many shrink passes budget_tool_result will attempt (each pass halves
# the head/tail window) before giving up and returning whatever it has. A
# single head+tail pass can still leave a very wide row (e.g. a dict with a
# huge blob value) over max_chars; iterating gets closer without looping
# forever on a payload that can't be shrunk by row-count alone.
_MAX_SHRINK_PASSES = 4

# Tools whose result is a single nested object (verdict/positioning/regime
# summary, a quote), never a table — excluded by name rather than relying
# solely on the structural gate, since e.g. a quote's nested `reference` block
# could coincidentally contain a short list.
TOON_NEVER_TOOLS: frozenset[str] = frozenset(
    {
        "get_signal_study",
        "get_positioning_context",
        "get_market_regime_indicators",
        "get_macro_regime_indicators",
        "get_watchlist_context",
        "get_market_quote",
    }
)


class ToonBlock(str):
    """A raw TOON-encoded table (see ``encode_toon_table``).

    A plain ``str`` subclass so it composes transparently with ``dict``/
    ``list`` structures and existing ``isinstance(v, str)`` checks elsewhere —
    but it must never be handed to plain ``json.dumps``/``compact_json``:
    that quotes and escapes it like any other string, which both bloats it
    past the JSON-escaped length and destroys its readability as a table. Use
    ``compact_json_with_toon`` for anything that might contain one.
    """

    __slots__ = ()


def toon_tabular_enabled() -> bool:
    raw = os.environ.get("COPINANCEOS_TOON_TABULAR_ENABLED", "")
    return raw.strip().lower() in ("1", "true", "yes")


def compact_json(obj: Any) -> str:
    """Dense JSON (no indentation) for a model-facing payload.

    Only safe for a structure that cannot contain a ``ToonBlock`` — use
    ``compact_json_with_toon`` otherwise (``budget_tool_result``'s output
    always might, so provider loops should call that instead of this
    directly on a tool result).
    """
    return json.dumps(obj, separators=(",", ":"), default=str)


def _split_toon_blocks(obj: Any, path: str = "$") -> tuple[Any, list[tuple[str, str]]]:
    """Recursively pull ``ToonBlock`` leaves out of ``obj``, replacing each
    with a short placeholder string and returning the extracted
    ``(path, block_text)`` pairs in traversal order."""
    if isinstance(obj, ToonBlock):
        return f"<see {path} below>", [(path, str(obj))]
    if isinstance(obj, dict):
        cleaned: dict[str, Any] = {}
        blocks: list[tuple[str, str]] = []
        for k, v in obj.items():
            cleaned_v, sub_blocks = _split_toon_blocks(v, f"{path}.{k}")
            cleaned[k] = cleaned_v
            blocks.extend(sub_blocks)
        return cleaned, blocks
    if isinstance(obj, list):
        cleaned_list: list[Any] = []
        blocks = []
        for i, v in enumerate(obj):
            cleaned_v, sub_blocks = _split_toon_blocks(v, f"{path}[{i}]")
            cleaned_list.append(cleaned_v)
            blocks.extend(sub_blocks)
        return cleaned_list, blocks
    return obj, []


def compact_json_with_toon(obj: Any) -> str:
    """Serialize ``obj`` for a model-facing message, splicing any
    ``ToonBlock`` in as raw text after the (compact JSON) envelope instead of
    escaping it inline. Degrades to plain ``compact_json`` when there are no
    TOON blocks, so it is safe to use unconditionally on any tool result."""
    cleaned, blocks = _split_toon_blocks(obj)
    header = compact_json(cleaned)
    if not blocks:
        return header
    parts = [header]
    for path, block in blocks:
        parts.append(f"\n--- {path} (table) ---\n{block}")
    return "\n".join(parts)


def _is_tabular_eligible(rows: list[Any]) -> bool:
    if len(rows) < _MIN_ROWS_FOR_TABULAR:
        return False
    if not all(isinstance(r, dict) for r in rows):
        return False
    columns = {k for r in rows for k in r}
    return len(columns) >= _MIN_COLUMNS_FOR_TABULAR


def _truncate_list(items: list[Any], *, head: int, tail: int) -> tuple[list[Any], int]:
    if len(items) <= head + tail:
        return items, 0
    kept = items[:head] + items[-tail:] if tail else items[:head]
    return kept, len(items) - len(kept)


def _tabularize_rows(name: str, rows: list[dict[str, Any]], *, head: int, tail: int) -> ToonBlock:
    """Truncate ``rows`` to a head+tail window *before* encoding — the row
    count must be bounded before this ever becomes a string, since nothing
    downstream can truncate a ``ToonBlock`` the way it can a list."""
    kept, omitted = _truncate_list(rows, head=head, tail=tail)
    encoded = encode_toon_table(name, kept)
    if omitted <= 0:
        return ToonBlock(encoded)
    note = (
        f"# truncated: showing {len(kept)} of {len(rows)} rows "
        f"(first {head}, last {tail}; {omitted} omitted)\n"
    )
    return ToonBlock(note + encoded)


def _maybe_tabularize(data: Any, tool_name: str, *, head: int = 60, tail: int = 20) -> Any:
    if not toon_tabular_enabled() or tool_name in TOON_NEVER_TOOLS:
        return data

    if isinstance(data, list):
        if _is_tabular_eligible(data):
            return _tabularize_rows(tool_name or "items", data, head=head, tail=tail)
        return data

    if isinstance(data, dict):
        out: dict[str, Any] | None = None
        for key, value in data.items():
            if isinstance(value, list) and _is_tabular_eligible(value):
                if out is None:
                    out = dict(data)
                out[key] = _tabularize_rows(key, value, head=head, tail=tail)
        return out if out is not None else data

    return data


def _truncate_non_tabular(data: Any) -> Any:
    """The pre-TOON truncation fallback: bare list -> head+tail with markers;
    dict -> truncate its large list-valued fields. Never touches a
    ``ToonBlock`` (it isn't a ``list``), which is correct — a TOON block was
    already bounded at encode time by ``_tabularize_rows``."""
    if isinstance(data, list):
        kept, omitted = _truncate_list(data, head=60, tail=20)
        if omitted <= 0:
            return data
        return {
            "_truncated": True,
            "_total_items": len(data),
            "_items_shown": len(kept),
            "_omitted": omitted,
            "data": kept,
            "note": (
                f"Response truncated: showing {len(kept)} of {len(data)} items (first 60, last 20)."
            ),
        }

    if isinstance(data, dict):
        list_keys = [
            k
            for k, v in data.items()
            if isinstance(v, list) and len(v) > _LIST_MIN_SIZE_TO_TRUNCATE
        ]
        if not list_keys:
            return data
        out = dict(data)
        truncated_fields: dict[str, Any] = {}
        for key in list_keys:
            items = data[key]
            kept, omitted = _truncate_list(items, head=40, tail=10)
            if omitted <= 0:
                continue
            out[key] = kept
            truncated_fields[key] = {
                "total_items": len(items),
                "items_shown": len(kept),
                "omitted": omitted,
            }
        if truncated_fields:
            out["_truncated"] = True
            out["_truncated_fields"] = truncated_fields
        return out

    return data


def per_call_max_chars(batch_size: int, *, total_budget: int = DEFAULT_MAX_RESULT_CHARS) -> int:
    """Split a per-turn character budget evenly across ``batch_size`` calls.

    Every provider loop calls this once per iteration (with the number of
    tool calls the model just made in that turn) and passes the result as
    ``budget_tool_result(..., max_chars=...)`` for each one — otherwise
    ``DEFAULT_MAX_RESULT_CHARS`` applied independently per call means a turn
    with N parallel calls can return N times the intended budget, which is
    exactly what ToolRuntime's parallel execution makes possible where the
    old serial loop made it self-limiting.
    """
    if batch_size <= 1:
        return total_budget
    return max(_MIN_PER_CALL_CHARS, total_budget // batch_size)


def budget_tool_result(
    data: Any, *, tool_name: str = "", max_chars: int = DEFAULT_MAX_RESULT_CHARS
) -> Any:
    """Downsample ``data`` so it stays near ``max_chars`` once rendered via
    ``compact_json_with_toon`` (the size check below uses that renderer, not
    plain ``compact_json`` — the two differ once a TOON block is involved,
    and only the TOON-aware size is the one that will actually reach the
    model).

    Tabularizes eligible arrays into TOON first (see module docstring; no-op
    unless ``COPINANCEOS_TOON_TABULAR_ENABLED`` is set — rows are truncated
    to a head+tail window *before* encoding, so a TOON block can't itself be
    the reason this is over budget), then, if still over budget:

    - A bare list truncates to a head+tail window with ``_truncated``/
      ``_total_items``/``_items_shown``/``_omitted`` markers.
    - A dict truncates whichever top-level list-valued fields are large
      enough to matter, each getting its own ``_truncated_fields[key]`` entry.
    - If a single pass still leaves it over budget (a dict with very wide
      individual rows, say), the head+tail window shrinks and both stages
      repeat, up to ``_MAX_SHRINK_PASSES`` times.
    """
    head, tail = 60, 20
    result = data
    for attempt in range(_MAX_SHRINK_PASSES):
        tabularized = _maybe_tabularize(data, tool_name, head=head, tail=tail)
        result = _truncate_non_tabular(tabularized)
        under_budget = len(compact_json_with_toon(result)) <= max_chars
        if under_budget or head <= 5 or attempt == _MAX_SHRINK_PASSES - 1:
            return result
        head, tail = max(5, head // 2), max(2, tail // 2)
    return result
