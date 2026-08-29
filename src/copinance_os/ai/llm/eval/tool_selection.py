"""Tool-selection eval harness — the missing safety net called for by the
"faster, more reliable AI tool system" design doc (§7): there were no AI evals
of any kind before this, so any change to tool schemas, prompt framing, or the
agent loop was flying blind on whether the model still picks the right tools.

Two tiers, both driving the exact same ``run_tool_selection_eval`` runner:

- **Fake-provider tier** (fast, deterministic, runs in CI — see
  ``tests/unit/copinance_os/ai/llm/eval/test_tool_selection_eval.py``): a
  scripted ``LLMProvider`` returns a canned tool-call list per question,
  bypassing real inference entirely. This does not test model judgment — it
  tests the harness itself (comparison/aggregation logic, dataset shape) so
  that logic isn't only ever exercised the first time someone points it at a
  real model.
- **Real-model tier** (``@pytest.mark.llm``, opt-in, needs an API key): drives
  an actual provider end to end and scores its real tool choices. This is
  where tool-selection judgment is actually measured, and it must run per
  provider (Gemini/OpenAI/Anthropic) separately — selection quality is
  model-dependent, so a pass on one provider is not evidence for another.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from copinance_os.ai.llm.providers.base import LLMProvider
from copinance_os.domain.ports.tools import Tool


@dataclass(frozen=True)
class ToolSelectionCase:
    """One (question -> expected tool set) eval case.

    ``acceptable_extra_tools`` covers legitimate alternates the model might
    reasonably reach for instead of (or alongside) the primary expected
    tool(s) — e.g. ``get_current_date`` as a harmless grounding call, or two
    tools that both plausibly answer an ambiguous question. Anything outside
    ``expected_tools | acceptable_extra_tools`` counts as an unexpected call.
    """

    id: str
    question: str
    expected_tools: frozenset[str]
    acceptable_extra_tools: frozenset[str] = frozenset()
    tags: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ToolSelectionResult:
    case_id: str
    question: str
    expected_tools: frozenset[str]
    actual_tools: frozenset[str]
    missing: frozenset[str]
    unexpected: frozenset[str]
    error: str | None = None

    @property
    def passed(self) -> bool:
        return self.error is None and not self.missing and not self.unexpected


@dataclass(frozen=True)
class ToolSelectionReport:
    provider_name: str
    results: list[ToolSelectionResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 1.0
        return sum(1 for r in self.results if r.passed) / len(self.results)

    @property
    def failures(self) -> list[ToolSelectionResult]:
        return [r for r in self.results if not r.passed]

    def summary(self) -> str:
        n = len(self.results)
        passed = n - len(self.failures)
        lines = [f"{self.provider_name}: {passed}/{n} passed ({self.pass_rate:.0%})"]
        for r in self.failures:
            detail = r.error or f"missing={sorted(r.missing)} unexpected={sorted(r.unexpected)}"
            lines.append(f"  FAIL [{r.case_id}] {r.question!r}: {detail}")
        return "\n".join(lines)


def _extract_called_tool_names(llm_result: dict[str, Any]) -> frozenset[str]:
    names = set()
    for tc in llm_result.get("tool_calls", []) or []:
        name = tc.get("tool") if isinstance(tc, dict) else None
        if isinstance(name, str) and name:
            names.add(name)
    return frozenset(names)


async def run_tool_selection_eval(
    provider: LLMProvider,
    tools: list[Tool],
    cases: list[ToolSelectionCase],
    *,
    system_prompt: str | None = None,
    max_iterations: int = 2,
) -> ToolSelectionReport:
    """Run every case against ``provider`` and score which tools it called.

    ``max_iterations`` defaults low (2, not the usual 5) — this evaluates tool
    *selection*, not full multi-turn analysis, so it only needs enough
    iterations to see the model's first-round (and one follow-up) tool
    choices, not a complete answer.
    """
    results: list[ToolSelectionResult] = []
    for case in cases:
        try:
            llm_result = await provider.generate_with_tools(
                prompt=case.question,
                tools=tools,
                system_prompt=system_prompt,
                max_iterations=max_iterations,
            )
        except Exception as e:
            results.append(
                ToolSelectionResult(
                    case_id=case.id,
                    question=case.question,
                    expected_tools=case.expected_tools,
                    actual_tools=frozenset(),
                    missing=case.expected_tools,
                    unexpected=frozenset(),
                    error=str(e),
                )
            )
            continue

        actual = _extract_called_tool_names(llm_result)
        allowed = case.expected_tools | case.acceptable_extra_tools
        results.append(
            ToolSelectionResult(
                case_id=case.id,
                question=case.question,
                expected_tools=case.expected_tools,
                actual_tools=actual,
                missing=case.expected_tools - actual,
                unexpected=actual - allowed,
            )
        )

    return ToolSelectionReport(provider_name=provider.get_provider_name(), results=results)
