"""LLM generator for curated follow-up questions."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import structlog

from copinance_os.ai.llm.policy import NUMERIC_GROUNDING_POLICY
from copinance_os.ai.llm.providers.base import LLMProvider
from copinance_os.ai.llm.resources import PromptManager
from copinance_os.domain.literacy import financial_literacy_prompt_value, resolve_financial_literacy
from copinance_os.domain.models.curated_questions import (
    ArtifactType,
    CuratedQuestion,
    CuratedQuestionsBlock,
    CuratedQuestionsMeta,
    LLMUnavailableReason,
    filter_suggested_tools,
    utc_now,
)
from copinance_os.domain.models.profile import FinancialLiteracy

logger = structlog.get_logger(__name__)

CURATED_QUESTIONS_PROMPT_NAME = "curated_questions"
_GENERATION_TIMEOUT_SECONDS = 45.0


def _extract_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", stripped)
    if not match:
        return None
    try:
        parsed = json.loads(match.group())
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _classify_provider_error(exc: BaseException) -> LLMUnavailableReason:
    msg = str(exc).lower()
    if "rate" in msg and "limit" in msg:
        return LLMUnavailableReason.RATE_LIMITED
    if "timeout" in msg or "timed out" in msg:
        return LLMUnavailableReason.TIMEOUT
    return LLMUnavailableReason.PROVIDER_ERROR


class CuratedQuestionsGenerator:
    """Generate curated questions from a deterministic data summary."""

    def __init__(
        self,
        *,
        allowed_tool_names: frozenset[str],
        prompt_manager: PromptManager | None = None,
    ) -> None:
        self._prompt_manager = prompt_manager or PromptManager()
        self._allowed_tools = allowed_tool_names

    async def generate(
        self,
        *,
        artifact: ArtifactType,
        context_summary: dict[str, Any],
        count: int,
        financial_literacy: FinancialLiteracy | None,
        learning_step: int | None,
        llm_provider: LLMProvider | None,
    ) -> CuratedQuestionsBlock:
        lit = resolve_financial_literacy(financial_literacy)
        meta_base = CuratedQuestionsMeta(
            artifact=artifact,
            requested_count=count,
            llm_enabled=False,
            llm_unavailable_reason=None,
            generated_at=None,
            cache_hit=False,
            numeric_grounding_policy=NUMERIC_GROUNDING_POLICY,
        )

        if llm_provider is None:
            logger.warning(
                "Curated questions skipped: no LLM provider",
                artifact=artifact.value,
            )
            return CuratedQuestionsBlock(
                questions=[],
                meta=meta_base.model_copy(
                    update={"llm_unavailable_reason": LLMUnavailableReason.NO_LLM_CONFIG}
                ),
            )

        try:
            available = await llm_provider.is_available()
        except Exception as exc:
            logger.warning(
                "Curated questions LLM availability check failed",
                artifact=artifact.value,
                error=str(exc),
            )
            return CuratedQuestionsBlock(
                questions=[],
                meta=meta_base.model_copy(
                    update={
                        "llm_unavailable_reason": _classify_provider_error(exc),
                    }
                ),
            )

        if not available:
            # Provider was configured but failed its health check (e.g. invalid API key).
            logger.warning(
                "Curated questions skipped: LLM provider not available",
                artifact=artifact.value,
            )
            return CuratedQuestionsBlock(
                questions=[],
                meta=meta_base.model_copy(
                    update={"llm_unavailable_reason": LLMUnavailableReason.PROVIDER_ERROR}
                ),
            )

        learning_step_line = (
            f"Dashboard learning step: {learning_step}." if learning_step is not None else ""
        )
        data_json = json.dumps(context_summary, default=str)
        tools_csv = ", ".join(sorted(self._allowed_tools))
        system_prompt, user_prompt = self._prompt_manager.get_prompt(
            CURATED_QUESTIONS_PROMPT_NAME,
            financial_literacy=financial_literacy_prompt_value(lit),
            learning_step_line=learning_step_line,
            numeric_grounding_policy=NUMERIC_GROUNDING_POLICY,
            allowed_tools=tools_csv,
            artifact_type=artifact.value,
            question_count=str(count),
            data_json=data_json,
        )

        try:
            async with asyncio.timeout(_GENERATION_TIMEOUT_SECONDS):
                raw = await llm_provider.generate_text(
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    temperature=0.3,
                    max_tokens=768,
                )
        except TimeoutError:
            logger.warning("Curated questions LLM timed out", artifact=artifact.value)
            return CuratedQuestionsBlock(
                questions=[],
                meta=meta_base.model_copy(
                    update={"llm_unavailable_reason": LLMUnavailableReason.TIMEOUT}
                ),
            )
        except Exception as exc:
            reason = _classify_provider_error(exc)
            logger.warning(
                "Curated questions LLM call failed",
                artifact=artifact.value,
                reason=reason.value,
                error=str(exc),
            )
            return CuratedQuestionsBlock(
                questions=[],
                meta=meta_base.model_copy(update={"llm_unavailable_reason": reason}),
            )

        parsed = _extract_json_object(raw)
        if parsed is None:
            logger.warning(
                "Curated questions parse failed",
                artifact=artifact.value,
            )
            return CuratedQuestionsBlock(
                questions=[],
                meta=meta_base.model_copy(
                    update={"llm_unavailable_reason": LLMUnavailableReason.PARSE_ERROR}
                ),
            )

        raw_questions = parsed.get("questions")
        if not isinstance(raw_questions, list):
            return CuratedQuestionsBlock(
                questions=[],
                meta=meta_base.model_copy(
                    update={"llm_unavailable_reason": LLMUnavailableReason.PARSE_ERROR}
                ),
            )

        questions: list[CuratedQuestion] = []
        for item in raw_questions[:count]:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if not isinstance(text, str) or not text.strip():
                continue
            tools_raw = item.get("suggested_tools")
            tools_list: list[str] | None = None
            if isinstance(tools_raw, list):
                tools_list = [str(t) for t in tools_raw if isinstance(t, str)]
            elif tools_raw is None:
                tools_list = None
            else:
                tools_list = None
            filtered_tools = filter_suggested_tools(tools_list, self._allowed_tools)
            requires = item.get("requires_symbol")
            requires_symbol = (
                str(requires).upper()[:32]
                if requires is not None and str(requires).strip()
                else None
            )
            try:
                questions.append(
                    CuratedQuestion(
                        text=text.strip()[:500],
                        focus=(str(item["focus"])[:120] if item.get("focus") is not None else None),
                        suggested_tools=filtered_tools,
                        requires_symbol=requires_symbol,
                    )
                )
            except Exception:
                continue

        return CuratedQuestionsBlock(
            questions=questions,
            meta=meta_base.model_copy(
                update={
                    "llm_enabled": True,
                    "generated_at": utc_now(),
                }
            ),
        )
