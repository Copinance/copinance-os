"""TOON vs. compact-JSON retrieval-accuracy A/B — the eval the design doc's
TOON assessment calls "the gate that decides whether TOON ships default-on."

The token-count savings TOON gives on rectangular payloads (options chains,
OHLCV bars) are already measured and real (see ``tool_result_serialization.py``'s
module docstring). What isn't measured — and can't be, without hitting a real
model — is whether a model's *retrieval accuracy* against a TOON-encoded table
holds up as well as against JSON. Independent benchmarking found TOON can
actually rank *below* plain JSON on some payload shapes, and that the effect
is model-dependent. This module is the harness for settling that per model,
not an assumption either way.

Two tiers, mirroring ``tool_selection.py``:

- **Fake-provider tier** (see ``test_format_ab_eval.py``): a scripted
  provider with a canned answer per (case, format) pair. Deterministic, no
  network — it validates the harness's own scoring/aggregation, not model
  behavior.
- **Real-model tier** (``@pytest.mark.llm``): asks an actual provider a
  retrieval question against the same payload rendered two ways, and scores
  whether the answer contains the expected value. This is where the real A/B
  signal comes from, and it must be run **per provider** — a pass on one
  model is not evidence for another.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from copinance_os.ai.llm.providers.base import LLMProvider
from copinance_os.ai.llm.tool_result_serialization import compact_json
from copinance_os.ai.llm.toon_encoding import encode_toon_table

FormatName = Literal["compact_json", "toon"]


@dataclass(frozen=True)
class FormatAbCase:
    """One retrieval question against one payload, scored per format."""

    id: str
    rows: list[dict[str, Any]]
    table_name: str
    question: str
    expected_answer: str


@dataclass(frozen=True)
class FormatAbResult:
    case_id: str
    format_name: FormatName
    passed: bool
    answer: str
    error: str | None = None


@dataclass(frozen=True)
class FormatAbReport:
    provider_name: str
    results: list[FormatAbResult] = field(default_factory=list)

    def pass_rate_for(self, format_name: FormatName) -> float:
        subset = [r for r in self.results if r.format_name == format_name]
        if not subset:
            return 1.0
        return sum(1 for r in subset if r.passed) / len(subset)

    def summary(self) -> str:
        lines = [f"{self.provider_name}:"]
        formats: tuple[FormatName, ...] = ("compact_json", "toon")
        for fmt in formats:
            lines.append(f"  {fmt}: {self.pass_rate_for(fmt):.0%}")
        for r in self.results:
            if not r.passed:
                detail = r.error or f"got {r.answer!r}"
                lines.append(f"  FAIL [{r.case_id}/{r.format_name}]: {detail}")
        return "\n".join(lines)


def render_payload(rows: list[dict[str, Any]], table_name: str, format_name: FormatName) -> str:
    if format_name == "toon":
        return encode_toon_table(table_name, rows)
    return compact_json({table_name: rows})


_RETRIEVAL_SYSTEM_PROMPT = (
    "Answer the question using only the data provided. Reply with the exact "
    "value only — no explanation, no punctuation, no extra words."
)


async def run_format_ab_eval(
    provider: LLMProvider,
    cases: list[FormatAbCase],
    *,
    formats: tuple[FormatName, ...] = ("compact_json", "toon"),
) -> FormatAbReport:
    results: list[FormatAbResult] = []
    for case in cases:
        for fmt in formats:
            rendered = render_payload(case.rows, case.table_name, fmt)
            prompt = f"Data:\n{rendered}\n\nQuestion: {case.question}"
            try:
                answer = await provider.generate_text(
                    prompt, system_prompt=_RETRIEVAL_SYSTEM_PROMPT
                )
            except Exception as e:
                results.append(
                    FormatAbResult(
                        case_id=case.id, format_name=fmt, passed=False, answer="", error=str(e)
                    )
                )
                continue
            passed = case.expected_answer.strip().lower() in answer.strip().lower()
            results.append(
                FormatAbResult(case_id=case.id, format_name=fmt, passed=passed, answer=answer)
            )
    return FormatAbReport(provider_name=provider.get_provider_name(), results=results)
