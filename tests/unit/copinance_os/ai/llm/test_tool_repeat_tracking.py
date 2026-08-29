"""ToolRepeatTracker: count-then-stop repeat detection, not detect-and-abort.

Design doc §6: the second identical call reuses the cached prior result
(plus a nudge); only a third ends the round. Parallel execution can fill the
old detect-on-first-sight window in a single iteration, making a legitimate
repeat kill the run — this is the fix.
"""

from __future__ import annotations

from copinance_os.ai.llm.tool_repeat_tracking import ToolRepeatTracker


def test_first_occurrence_does_not_stop() -> None:
    tracker: ToolRepeatTracker[str] = ToolRepeatTracker()
    assert tracker.record("get_quote", {"symbol": "AAPL"}) == 1
    assert tracker.should_stop("get_quote", {"symbol": "AAPL"}) is False


def test_second_occurrence_does_not_stop() -> None:
    tracker: ToolRepeatTracker[str] = ToolRepeatTracker()
    tracker.record("get_quote", {"symbol": "AAPL"})
    assert tracker.record("get_quote", {"symbol": "AAPL"}) == 2
    assert tracker.should_stop("get_quote", {"symbol": "AAPL"}) is False


def test_third_occurrence_stops() -> None:
    tracker: ToolRepeatTracker[str] = ToolRepeatTracker()
    tracker.record("get_quote", {"symbol": "AAPL"})
    tracker.record("get_quote", {"symbol": "AAPL"})
    assert tracker.record("get_quote", {"symbol": "AAPL"}) == 3
    assert tracker.should_stop("get_quote", {"symbol": "AAPL"}) is True


def test_stop_after_is_configurable() -> None:
    tracker: ToolRepeatTracker[str] = ToolRepeatTracker(stop_after=2)
    tracker.record("get_quote", {"symbol": "AAPL"})
    tracker.record("get_quote", {"symbol": "AAPL"})
    assert tracker.should_stop("get_quote", {"symbol": "AAPL"}) is True


def test_different_args_are_independent_signatures() -> None:
    tracker: ToolRepeatTracker[str] = ToolRepeatTracker()
    tracker.record("get_quote", {"symbol": "AAPL"})
    tracker.record("get_quote", {"symbol": "AAPL"})
    # MSFT has never been seen — a batch that also asks about AAPL a third
    # time must not spuriously stop MSFT's tracking.
    assert tracker.record("get_quote", {"symbol": "MSFT"}) == 1
    assert tracker.should_stop("get_quote", {"symbol": "MSFT"}) is False


def test_different_tool_names_are_independent_signatures() -> None:
    tracker: ToolRepeatTracker[str] = ToolRepeatTracker()
    tracker.record("get_quote", {"symbol": "AAPL"})
    assert tracker.record("get_chain", {"symbol": "AAPL"}) == 1


def test_a_full_parallel_batch_of_three_distinct_calls_never_stops_any_of_them() -> None:
    """The exact scenario parallelism introduced: one iteration issuing 3-4
    calls at once used to fill the entire max_recent_history=3 window,
    making any repeat on the *next* iteration look like a loop. Three
    distinct signatures in one batch must not trip should_stop for any of
    them."""
    tracker: ToolRepeatTracker[str] = ToolRepeatTracker()
    calls = [
        ("get_quote", {"symbol": "AAPL"}),
        ("get_chain", {"symbol": "AAPL"}),
        ("get_quote", {"symbol": "MSFT"}),
    ]
    for name, args in calls:
        tracker.record(name, args)
    assert not any(tracker.should_stop(name, args) for name, args in calls)


def test_remember_and_cached_round_trip() -> None:
    tracker: ToolRepeatTracker[dict] = ToolRepeatTracker()
    tracker.record("get_quote", {"symbol": "AAPL"})
    tracker.remember("get_quote", {"symbol": "AAPL"}, {"price": 100})
    assert tracker.cached("get_quote", {"symbol": "AAPL"}) == {"price": 100}


def test_cached_returns_none_when_never_remembered() -> None:
    tracker: ToolRepeatTracker[dict] = ToolRepeatTracker()
    assert tracker.cached("get_quote", {"symbol": "AAPL"}) is None


def test_signature_key_is_order_independent_over_args() -> None:
    tracker: ToolRepeatTracker[str] = ToolRepeatTracker()
    tracker.record("get_chain", {"symbol": "AAPL", "side": "call"})
    assert tracker.record("get_chain", {"side": "call", "symbol": "AAPL"}) == 2
