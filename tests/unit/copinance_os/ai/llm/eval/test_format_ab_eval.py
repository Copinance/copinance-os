"""TOON vs. compact-JSON retrieval A/B: two tiers over the same dataset
(format_ab_cases.py) and the same run_format_ab_eval runner.

Fake-provider tier (below, always runs): validates the harness itself. Real
answers to these retrieval questions can only come from an actual model —
see test_real_model_format_ab_smoke for that.
"""

from __future__ import annotations

import os
from typing import Any

import pytest

from copinance_os.ai.llm.eval import render_payload, run_format_ab_eval
from copinance_os.ai.llm.providers.anthropic import AnthropicProvider
from copinance_os.ai.llm.providers.base import LLMProvider
from copinance_os.ai.llm.providers.gemini import GeminiProvider
from copinance_os.ai.llm.providers.openai import OpenAIProvider

from .format_ab_cases import FORMAT_AB_CASES


def test_dataset_has_both_payload_shapes() -> None:
    table_names = {c.table_name for c in FORMAT_AB_CASES}
    assert table_names == {"calls", "bars"}


def test_dataset_cases_have_unique_ids() -> None:
    ids = [c.id for c in FORMAT_AB_CASES]
    assert len(ids) == len(set(ids))


def test_render_payload_toon_contains_expected_answer_value() -> None:
    """Sanity check on the dataset itself: the value the question asks for
    must actually appear in the rendered payload, in both formats — otherwise
    a "fail" would be meaningless (no model could ever answer it)."""
    case = FORMAT_AB_CASES[0]
    toon_rendered = render_payload(case.rows, case.table_name, "toon")
    json_rendered = render_payload(case.rows, case.table_name, "compact_json")
    assert case.expected_answer in toon_rendered
    assert case.expected_answer in json_rendered


class _FakeProvider(LLMProvider):
    """Returns a canned answer per prompt substring — no real inference."""

    def __init__(self, answer_for_toon: str, answer_for_json: str) -> None:
        self._answer_for_toon = answer_for_toon
        self._answer_for_json = answer_for_json

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        # TOON's header syntax (`name[N]{cols}:`) vs JSON's braces-first shape
        # is enough to tell which rendering this prompt embeds.
        if "]{" in prompt:
            return self._answer_for_toon
        return self._answer_for_json

    async def is_available(self) -> bool:
        return True

    def get_provider_name(self) -> str:
        return "fake"


@pytest.mark.asyncio
async def test_fake_provider_scores_correct_answer_as_passing() -> None:
    case = FORMAT_AB_CASES[0]
    provider = _FakeProvider(
        answer_for_toon=case.expected_answer, answer_for_json=case.expected_answer
    )

    report = await run_format_ab_eval(provider, [case])

    assert report.pass_rate_for("toon") == 1.0
    assert report.pass_rate_for("compact_json") == 1.0


@pytest.mark.asyncio
async def test_fake_provider_scores_wrong_answer_as_failing() -> None:
    case = FORMAT_AB_CASES[0]
    provider = _FakeProvider(answer_for_toon="wrong-value", answer_for_json="wrong-value")

    report = await run_format_ab_eval(provider, [case])

    assert report.pass_rate_for("toon") == 0.0
    assert report.pass_rate_for("compact_json") == 0.0


@pytest.mark.asyncio
async def test_fake_provider_can_score_formats_differently() -> None:
    """The whole point of the harness: it must be able to show TOON and JSON
    diverging on the same case, since that divergence is the actual signal
    the real-model tier is trying to measure."""
    case = FORMAT_AB_CASES[0]
    provider = _FakeProvider(answer_for_toon=case.expected_answer, answer_for_json="wrong")

    report = await run_format_ab_eval(provider, [case])

    assert report.pass_rate_for("toon") == 1.0
    assert report.pass_rate_for("compact_json") == 0.0


@pytest.mark.asyncio
async def test_provider_error_is_recorded_as_failure_not_a_crash() -> None:
    class _RaisingProvider(LLMProvider):
        async def generate_text(
            self,
            prompt: str,
            system_prompt: str | None = None,
            temperature: float | None = None,
            max_tokens: int | None = None,
            **kwargs: Any,
        ) -> str:
            raise RuntimeError("provider exploded")

        async def is_available(self) -> bool:
            return True

        def get_provider_name(self) -> str:
            return "raising"

    report = await run_format_ab_eval(_RaisingProvider(), [FORMAT_AB_CASES[0]])

    assert report.pass_rate_for("toon") == 0.0
    failure = next(r for r in report.results if r.format_name == "toon")
    assert failure.error == "provider exploded"


@pytest.mark.asyncio
async def test_fake_provider_tier_runs_the_full_dataset_end_to_end() -> None:
    provider = _FakeProvider(answer_for_toon="x", answer_for_json="x")
    # Not scored for correctness here (canned answers won't match real
    # expected values) — this just guards that every case round-trips
    # through the runner without raising.
    report = await run_format_ab_eval(provider, FORMAT_AB_CASES)
    assert len(report.results) == len(FORMAT_AB_CASES) * 2  # both formats per case


# ---------------------------------------------------------------------------
# Real-model tier: opt-in, needs an API key, actual retrieval accuracy here.
# ---------------------------------------------------------------------------


def _build_smoke_provider() -> LLMProvider | None:
    gemini_key = os.environ.get("COPINANCEOS_GEMINI_API_KEY", "").strip()
    openai_key = os.environ.get("COPINANCEOS_OPENAI_API_KEY", "").strip()
    anthropic_key = os.environ.get("COPINANCEOS_ANTHROPIC_API_KEY", "").strip()
    if gemini_key:
        return GeminiProvider(api_key=gemini_key)
    if openai_key:
        return OpenAIProvider(api_key=openai_key)
    if anthropic_key:
        return AnthropicProvider(api_key=anthropic_key)
    return None


@pytest.mark.llm
@pytest.mark.asyncio
async def test_real_model_format_ab_smoke() -> None:
    provider = _build_smoke_provider()
    if provider is None:
        pytest.skip(
            "No LLM API key configured (COPINANCEOS_GEMINI_API_KEY / "
            "COPINANCEOS_OPENAI_API_KEY / COPINANCEOS_ANTHROPIC_API_KEY) — "
            "real-model eval tier is opt-in."
        )

    report = await run_format_ab_eval(provider, FORMAT_AB_CASES)

    print(report.summary())
    # This is the actual A/B signal — not asserted here (that's a product
    # decision per the design doc, made from real report output), but a
    # collapse to near-zero on either format would indicate a broken harness
    # or a prompt that doesn't work at all, which IS worth failing on.
    assert report.pass_rate_for("compact_json") > 0.0 or report.pass_rate_for("toon") > 0.0
