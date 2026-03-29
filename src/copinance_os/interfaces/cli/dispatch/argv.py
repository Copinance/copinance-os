"""Parse ``sys.argv`` for the root ``copinance`` entry: Typer subcommands vs generic research."""

from __future__ import annotations

import sys
from dataclasses import dataclass

# Must stay in sync with lazy-loaded subcommands in ``interfaces.cli.root`` and ``version``.
KNOWN_ROOT_SUBCOMMANDS = frozenset({"analyze", "cache", "market", "profile", "version"})


@dataclass(frozen=True)
class GenericInvocation:
    """Natural-language question for question-driven market analysis (full tool suite)."""

    question: str
    json_output: bool
    include_prompt_in_results: bool
    stream: bool


@dataclass(frozen=True)
class TyperInvocation:
    """Delegate to the Typer app with these argv tokens (after ``copinance``)."""

    argv: list[str]


def parse_root_argv(argv: list[str]) -> GenericInvocation | TyperInvocation:
    """Decide whether to run generic research or the normal Typer CLI.

    Generic mode: first token is not a known subcommand and does not look like a root-only flag
    (except ``--json``, ``--stream``, and ``--include-prompt`` prefixes reserved for generic mode).

    Examples:
        ``["analyze", "equity", "AAPL"]`` → Typer
        ``["how", "is", "Tesla", "doing?"]`` → Generic
        ``["--json", "What", "is", "the", "VIX?"]`` → Generic with JSON
        ``["--stream", "What", "is", "the", "VIX?"]`` → Generic with streaming LLM output
    """
    if not argv:
        return TyperInvocation(argv=[])

    first = argv[0]

    if first in KNOWN_ROOT_SUBCOMMANDS:
        return TyperInvocation(argv=list(argv))

    if first in ("-h", "--help", "--version"):
        return TyperInvocation(argv=list(argv))

    # `copinance help` → same as --help (do not treat "help" as a research question).
    if first == "help" and len(argv) == 1:
        return TyperInvocation(argv=["--help"])

    # Root flags that are not generic questions: pass to Typer (may fail with unknown option).
    if first.startswith("-") and first not in ("--json", "--include-prompt", "--stream"):
        return TyperInvocation(argv=list(argv))

    json_output = False
    include_prompt = False
    stream = False
    rest = list(argv)
    while rest:
        head = rest[0]
        if head == "--json":
            json_output = True
            rest = rest[1:]
            continue
        if head == "--include-prompt":
            include_prompt = True
            rest = rest[1:]
            continue
        if head == "--stream":
            stream = True
            rest = rest[1:]
            continue
        break

    if not rest:
        print(
            "copinance: expected a research question after options.\n"
            '  Example: copinance "How is Tesla doing financially?"\n'
            '  Example: copinance --json "What is the 10-year yield?"\n'
            '  Example: copinance --stream "What is the VIX?"',
            file=sys.stderr,
        )
        raise SystemExit(2)

    question = " ".join(rest).strip()
    if not question:
        print("copinance: question is empty.", file=sys.stderr)
        raise SystemExit(2)

    return GenericInvocation(
        question=question,
        json_output=json_output,
        include_prompt_in_results=include_prompt,
        stream=stream and not json_output,
    )
