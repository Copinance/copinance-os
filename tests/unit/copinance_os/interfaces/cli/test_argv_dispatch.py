"""Tests for root argv dispatch (generic research vs Typer)."""

import pytest

from copinance_os.interfaces.cli.dispatch import (
    GenericInvocation,
    TyperInvocation,
    parse_root_argv,
)


@pytest.mark.unit
class TestParseRootArgv:
    def test_empty_delegates_to_typer(self) -> None:
        assert parse_root_argv([]) == TyperInvocation(argv=[])

    def test_known_subcommand_typer(self) -> None:
        assert parse_root_argv(["analyze", "equity", "X"]) == TyperInvocation(
            argv=["analyze", "equity", "X"]
        )
        assert parse_root_argv(["cache", "clear"]) == TyperInvocation(argv=["cache", "clear"])
        assert parse_root_argv(["market", "quote", "AAPL"]) == TyperInvocation(
            argv=["market", "quote", "AAPL"]
        )
        assert parse_root_argv(["profile", "list"]) == TyperInvocation(argv=["profile", "list"])
        assert parse_root_argv(["version"]) == TyperInvocation(argv=["version"])

    def test_help_flags_typer(self) -> None:
        assert parse_root_argv(["-h"]) == TyperInvocation(argv=["-h"])
        assert parse_root_argv(["--help"]) == TyperInvocation(argv=["--help"])
        assert parse_root_argv(["--version"]) == TyperInvocation(argv=["--version"])
        assert parse_root_argv(["help"]) == TyperInvocation(argv=["--help"])

    def test_unknown_flag_typer(self) -> None:
        assert parse_root_argv(["--unknown"]) == TyperInvocation(argv=["--unknown"])

    def test_natural_language_generic(self) -> None:
        r = parse_root_argv(["How", "is", "Tesla", "doing?"])
        assert isinstance(r, GenericInvocation)
        assert r.question == "How is Tesla doing?"
        assert r.json_output is False
        assert r.include_prompt_in_results is False
        assert r.stream is False

    def test_generic_with_json(self) -> None:
        r = parse_root_argv(["--json", "What", "is", "VIX?"])
        assert isinstance(r, GenericInvocation)
        assert r.question == "What is VIX?"
        assert r.json_output is True

    def test_generic_json_and_include_prompt(self) -> None:
        r = parse_root_argv(["--json", "--include-prompt", "Macro", "outlook"])
        assert isinstance(r, GenericInvocation)
        assert r.question == "Macro outlook"
        assert r.json_output is True
        assert r.include_prompt_in_results is True
        assert r.stream is False

    def test_generic_with_stream(self) -> None:
        r = parse_root_argv(["--stream", "What", "is", "the", "VIX?"])
        assert isinstance(r, GenericInvocation)
        assert r.question == "What is the VIX?"
        assert r.stream is True

    def test_generic_stream_disabled_with_json(self) -> None:
        r = parse_root_argv(["--json", "--stream", "Hello"])
        assert isinstance(r, GenericInvocation)
        assert r.json_output is True
        assert r.stream is False

    def test_only_json_exits(self) -> None:
        with pytest.raises(SystemExit) as ei:
            parse_root_argv(["--json"])
        assert ei.value.code == 2
