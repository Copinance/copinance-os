"""Cross-iteration repeat tracking for one tool-calling loop.

Every provider loop (``openai.py``, ``gemini.py``, ``anthropic.py``,
``ollama.py``) detects an unproductive loop the same way: track the last few
``(tool_name, args)`` signatures actually executed, and if the model repeats
one exactly, stop the whole run rather than let it spin. Before parallel
execution, that was a rare event — one call per iteration meant the "recent"
window filled slowly. Native function calling changed that: a single turn can
now issue 3-4 parallel calls at once, which can fill the entire
``max_recent_history`` window in one iteration. The very next legitimate
repeat — often not a loop at all, just the model re-checking something after
other calls informed a follow-up — then killed the run immediately.

Design doc §6's fix: "the second identical call returns the cached prior
result plus a nudge; only a third ends the round." ``ToolRepeatTracker``
holds the counting and the remembered result; each provider loop still owns
the reaction (skip execution and reuse a remembered result on the second
occurrence, stop the loop on the third) since that's tied into per-provider
message-building it isn't this module's job to know about.
"""

from __future__ import annotations

import json
from typing import Any, Generic, TypeVar

T = TypeVar("T")

DEFAULT_STOP_AFTER = 3

REPEAT_NOTICE = (
    "This exact tool call (same name and arguments) was already made earlier in this "
    "conversation turn — returning the same result rather than re-running it. If this "
    "keeps happening, stop calling this tool and answer from the data already available."
)


class ToolRepeatTracker(Generic[T]):
    """One instance per ``generate_with_tools()`` call — never shared across
    turns. Tracks how many times each ``(tool_name, args)`` signature has
    been *requested* so far (not how many times it actually ran — the second
    request for a signature is served from ``remember``'s cache, not
    re-executed), and remembers the first occurrence's result so a second
    request can reuse it.
    """

    def __init__(self, *, stop_after: int = DEFAULT_STOP_AFTER) -> None:
        self._stop_after = stop_after
        self._counts: dict[tuple[str, str], int] = {}
        self._results: dict[tuple[str, str], T] = {}

    @staticmethod
    def _key(name: str, args: dict[str, Any]) -> tuple[str, str]:
        return name, json.dumps(args, sort_keys=True, default=str)

    def record(self, name: str, args: dict[str, Any]) -> int:
        """Call once per planned call, before deciding whether to execute it.
        Returns the 1-based occurrence count for this exact signature."""
        key = self._key(name, args)
        count = self._counts.get(key, 0) + 1
        self._counts[key] = count
        return count

    def should_stop(self, name: str, args: dict[str, Any]) -> bool:
        return self._counts.get(self._key(name, args), 0) >= self._stop_after

    def remember(self, name: str, args: dict[str, Any], result: T) -> None:
        self._results[self._key(name, args)] = result

    def cached(self, name: str, args: dict[str, Any]) -> T | None:
        return self._results.get(self._key(name, args))
