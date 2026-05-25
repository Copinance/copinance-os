"""Financial literacy: resolve context values, tier deterministic copy, drive LLM tone.

**Where literacy is used today**

1. **Job / executor context** — ``DefaultJobRunner`` sets ``context["financial_literacy"]`` to the
   profile’s enum **value** (``beginner`` | ``intermediate`` | ``advanced``) when a profile is
   attached. Executors and tools should treat the key as optional and normalize via
   :func:`resolve_financial_literacy`.

2. **Deterministic analytics (structured JSON)** — When numeric pipelines need human-readable
   ``name`` / ``explanation`` / ``narrative`` fields at multiple depths, colocate **tiered
   strings** under ``data/literacy/`` (one module per feature). Use :class:`TieredCopy`
   and ``.pick(lit)`` so all three tiers stay in sync across instrument, market, macro,
   and options analysis surfaces.

3. **LLM prompts** — Question-driven flows pass ``{financial_literacy}`` and a tier-specific
   ``{literacy_output_contract}`` (see :func:`literacy_output_contract_for_question_driven`).
   Use :func:`financial_literacy_prompt_value` for the stable token string.

**Layering**

- :class:`TieredCopy` and resolution helpers live in **domain** (stdlib + enum only) so any layer
  may import them.
- Long prose tables stay in **data** (or **interfaces** for CLI copy), not in domain.

See also: ``.claude/rules/architecture.md`` (Financial literacy and narratives).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from copinance_os.domain.models.entities.profile import FinancialLiteracy

DEFAULT_LITERACY_FOR_ANALYSIS_OUTPUT: Final = FinancialLiteracy.INTERMEDIATE


@dataclass(frozen=True, slots=True)
class TieredCopy:
    """One idea expressed at beginner / intermediate / advanced depth."""

    beginner: str
    intermediate: str
    advanced: str

    def pick(self, lit: FinancialLiteracy) -> str:
        if lit == FinancialLiteracy.BEGINNER:
            return self.beginner
        if lit == FinancialLiteracy.ADVANCED:
            return self.advanced
        return self.intermediate


def resolve_financial_literacy(value: FinancialLiteracy | str | None) -> FinancialLiteracy:
    """Normalize job/tool context to a literacy enum.

    Unknown or missing values use :data:`DEFAULT_LITERACY_FOR_ANALYSIS_OUTPUT` so JSON fixtures
    and LLM tone stay aligned with the historical default for options positioning.
    """
    if value is None:
        return DEFAULT_LITERACY_FOR_ANALYSIS_OUTPUT
    if isinstance(value, FinancialLiteracy):
        return value
    try:
        return FinancialLiteracy(str(value).strip().lower())
    except ValueError:
        return DEFAULT_LITERACY_FOR_ANALYSIS_OUTPUT


def financial_literacy_prompt_value(value: FinancialLiteracy | str | None) -> str:
    """Return the stable string token for LLM system/user templates (e.g. ``{financial_literacy}``)."""
    return resolve_financial_literacy(value).value


def literacy_output_contract_for_question_driven(lit: FinancialLiteracy) -> str:
    """Hard output rules for question-driven prompts (injected as ``{literacy_output_contract}``)."""
    if lit == FinancialLiteracy.BEGINNER:
        return (
            "MANDATORY FOR THIS USER (beginner):\n"
            "- Lead the final answer with one plain-English sentence on what matters for them (no jargon).\n"
            "- Define every finance term the first time you use it (same sentence: term → plain meaning).\n"
            "- Prefer short sentences; use one analogy or everyday comparison when explaining a mechanism.\n"
            "- Prioritize 'what could go wrong / what to watch' over listing indicators; avoid acronym stacks.\n"
            "- Do not perform 'expert voice': if a simpler phrase exists, use it."
        )
    if lit == FinancialLiteracy.ADVANCED:
        return (
            "MANDATORY FOR THIS USER (advanced):\n"
            "- Use full institutional vocabulary and compact reasoning; skip tutorial definitions.\n"
            "- You may chain second-order effects, cross-asset context, and options-structure detail directly."
        )
    return (
        "MANDATORY FOR THIS USER (intermediate):\n"
        "- Use standard market terms; one short gloss when introducing a less common concept.\n"
        "- Mix intuition (price path, risk) with light structure (short bullets allowed)."
    )
