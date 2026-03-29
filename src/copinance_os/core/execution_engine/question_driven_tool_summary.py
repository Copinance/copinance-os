"""Deterministic display text when the LLM does not return a final prose answer."""

from __future__ import annotations

import json
from typing import Any


def is_tool_call_json_text(text: str) -> bool:
    """True if *text* looks like the project's JSON tool-call shape (not a natural answer)."""
    t = (text or "").strip()
    if not t.startswith("{"):
        return False
    try:
        obj = json.loads(t)
    except json.JSONDecodeError:
        return False
    if not isinstance(obj, dict):
        return False
    return "tool" in obj and "args" in obj


def summarize_tool_calls_for_display(
    tool_calls: list[dict[str, Any]], *, max_rows_per_tool: int = 25
) -> str:
    """Format successful tool payloads for human-readable console / markdown."""
    blocks: list[str] = []
    for tc in tool_calls:
        name = tc.get("tool", "?")
        ok = tc.get("success", True)
        err = tc.get("error")
        resp = tc.get("response")
        header = f"### {name}"
        if not ok:
            blocks.append(f"{header}\n**Failed:** {err}")
            continue
        body = _format_response(name, resp, max_rows_per_tool)
        blocks.append(f"{header}\n{body}")
    return "\n\n".join(blocks)


def _format_response(tool_name: str, resp: Any, max_rows: int) -> str:
    _ = tool_name
    if resp is None:
        return "_(no data)_"
    if isinstance(resp, dict) and resp.get("_truncated") and isinstance(resp.get("data"), list):
        return _format_response(tool_name, resp["data"], max_rows) + f"\n\n_{resp.get('note', '')}_"
    if isinstance(resp, list) and resp and isinstance(resp[0], dict):
        sample = resp[0]
        if "accession_number" in sample and "form" in sample:
            lines = ["| Filing date | Form | Accession |", "| --- | --- | --- |"]
            for row in resp[:max_rows]:
                fd = row.get("filing_date", "")
                fm = row.get("form", "")
                acc = row.get("accession_number", "")
                lines.append(f"| {fd} | {fm} | {acc} |")
            if len(resp) > max_rows:
                lines.append("")
                lines.append(f"_… and {len(resp) - max_rows} more rows (full data in saved JSON)._")
            return "\n".join(lines)
        lines = []
        for row in resp[:max_rows]:
            compact = json.dumps(row, default=str)
            lines.append(f"- {compact[:500]}{'…' if len(compact) > 500 else ''}")
        if len(resp) > max_rows:
            lines.append(f"_… and {len(resp) - max_rows} more items._")
        return "\n".join(lines)
    if isinstance(resp, dict):
        truncated = json.dumps(resp, indent=2, default=str)
        if len(truncated) > 8000:
            return f"```json\n{truncated[:8000]}\n```\n… _(truncated)_"
        return f"```json\n{truncated}\n```"
    s = str(resp)
    return s[:4000] + ("…" if len(s) > 4000 else "")


def build_partial_synthesis_message(
    *,
    reason: str,
    error_detail: str | None,
    tool_calls: list[dict[str, Any]],
) -> str:
    """Markdown-friendly message: explain the gap and show tool data."""
    parts = [
        "**No model-written summary was produced.**",
        "",
        f"**Reason:** {reason}",
    ]
    if error_detail:
        parts.extend(["", f"**Detail:** `{error_detail}`"])
    parts.extend(
        [
            "",
            "---",
            "",
            "#### Data retrieved from tools",
            "",
            summarize_tool_calls_for_display(tool_calls),
        ]
    )
    return "\n".join(parts)
