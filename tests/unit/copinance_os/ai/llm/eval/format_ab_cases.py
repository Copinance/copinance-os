"""Format A/B eval dataset — retrieval questions against rectangular payloads
shaped like the two the TOON assessment measured: an options chain (strike
rows) and a daily OHLCV bar series. Used by both eval tiers in
test_format_ab_eval.py.
"""

from __future__ import annotations

from copinance_os.ai.llm.eval import FormatAbCase


def _options_chain_rows(n: int) -> list[dict[str, object]]:
    return [
        {
            "strike": 100 + i,
            "bid": round(5.0 - i * 0.1, 2),
            "ask": round(5.1 - i * 0.1, 2),
            "volume": 100 + i * 7,
            "open_interest": 500 + i * 3,
        }
        for i in range(n)
    ]


def _ohlcv_rows(n: int) -> list[dict[str, object]]:
    return [
        {
            "date": f"2024-01-{(i % 28) + 1:02d}",
            "open": round(100 + i * 0.5, 2),
            "high": round(101 + i * 0.5, 2),
            "low": round(99 + i * 0.5, 2),
            "close": round(100.5 + i * 0.5, 2),
            "volume": 1_000_000 + i * 1000,
        }
        for i in range(n)
    ]


_CHAIN_30 = _options_chain_rows(30)
_OHLCV_30 = _ohlcv_rows(30)

FORMAT_AB_CASES: list[FormatAbCase] = [
    FormatAbCase(
        id="chain-bid-at-strike-first-row",
        rows=_CHAIN_30,
        table_name="calls",
        question="What is the bid for the contract with strike 100?",
        expected_answer=str(_CHAIN_30[0]["bid"]),
    ),
    FormatAbCase(
        id="chain-bid-at-strike-last-row",
        rows=_CHAIN_30,
        table_name="calls",
        question=f"What is the bid for the contract with strike {_CHAIN_30[-1]['strike']}?",
        expected_answer=str(_CHAIN_30[-1]["bid"]),
    ),
    FormatAbCase(
        id="chain-bid-at-strike-middle-row",
        rows=_CHAIN_30,
        table_name="calls",
        question=f"What is the ask for the contract with strike {_CHAIN_30[15]['strike']}?",
        expected_answer=str(_CHAIN_30[15]["ask"]),
    ),
    FormatAbCase(
        id="chain-volume-lookup",
        rows=_CHAIN_30,
        table_name="calls",
        question=f"What is the volume for the contract with strike {_CHAIN_30[22]['strike']}?",
        expected_answer=str(_CHAIN_30[22]["volume"]),
    ),
    FormatAbCase(
        id="chain-open-interest-lookup",
        rows=_CHAIN_30,
        table_name="calls",
        question=(
            f"What is the open_interest for the contract with strike {_CHAIN_30[8]['strike']}?"
        ),
        expected_answer=str(_CHAIN_30[8]["open_interest"]),
    ),
    FormatAbCase(
        id="ohlcv-close-first-row",
        rows=_OHLCV_30,
        table_name="bars",
        question=f"What was the close on {_OHLCV_30[0]['date']}?",
        expected_answer=str(_OHLCV_30[0]["close"]),
    ),
    FormatAbCase(
        id="ohlcv-close-last-row",
        rows=_OHLCV_30,
        table_name="bars",
        question=f"What was the close on {_OHLCV_30[-1]['date']}?",
        expected_answer=str(_OHLCV_30[-1]["close"]),
    ),
    FormatAbCase(
        id="ohlcv-high-lookup",
        rows=_OHLCV_30,
        table_name="bars",
        question=f"What was the high on {_OHLCV_30[12]['date']}?",
        expected_answer=str(_OHLCV_30[12]["high"]),
    ),
    FormatAbCase(
        id="ohlcv-volume-lookup",
        rows=_OHLCV_30,
        table_name="bars",
        question=f"What was the volume on {_OHLCV_30[19]['date']}?",
        expected_answer=str(_OHLCV_30[19]["volume"]),
    ),
    FormatAbCase(
        id="ohlcv-low-lookup",
        rows=_OHLCV_30,
        table_name="bars",
        question=f"What was the low on {_OHLCV_30[25]['date']}?",
        expected_answer=str(_OHLCV_30[25]["low"]),
    ),
]
