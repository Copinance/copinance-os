"""Deterministic summaries for curated-questions generation."""

from copinance_os.data.curated_questions.context import build_context, cap_context_for_artifact
from copinance_os.data.curated_questions.limits import ARTIFACT_MAX_JSON_CHARS, DASHBOARD_ARTIFACTS

__all__ = [
    "ARTIFACT_MAX_JSON_CHARS",
    "DASHBOARD_ARTIFACTS",
    "build_context",
    "cap_context_for_artifact",
]
