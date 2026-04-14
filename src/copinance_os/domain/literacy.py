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

3. **LLM prompts** — Question-driven and similar flows pass a single string into templates (e.g.
   ``{financial_literacy}``). Use :func:`financial_literacy_prompt_value` so defaults and invalid
   tokens match deterministic analytics (intermediate default).

**Layering**

- :class:`TieredCopy` and resolution helpers live in **domain** (stdlib + enum only) so any layer
  may import them.
- Long prose tables stay in **data** (or **interfaces** for CLI copy), not in domain.

See also: ``.claude/rules/architecture.md`` (Financial literacy and narratives).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from copinance_os.domain.models.profile import FinancialLiteracy

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
