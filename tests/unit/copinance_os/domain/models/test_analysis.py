"""Tests for analysis request helpers and validation."""

import pytest

from copinance_os.domain.models.analysis import (
    AnalyzeInstrumentRequest,
    AnalyzeMode,
    merge_instrument_expiration_inputs,
)
from copinance_os.domain.models.market import MarketType, OptionSide


@pytest.mark.unit
def test_merge_instrument_expiration_inputs_dedupes_and_order() -> None:
    assert merge_instrument_expiration_inputs("2026-06-19", ["2026-07-17", "2026-06-19"]) == [
        "2026-07-17",
        "2026-06-19",
    ]


@pytest.mark.unit
def test_merge_instrument_expiration_inputs_invalid_date_raises() -> None:
    with pytest.raises(ValueError):
        merge_instrument_expiration_inputs("2026-13-01", None)


@pytest.mark.unit
def test_analyze_instrument_request_accepts_multiple_option_expirations() -> None:
    r = AnalyzeInstrumentRequest(
        symbol="AAPL",
        market_type=MarketType.OPTIONS,
        mode=AnalyzeMode.DETERMINISTIC,
        expiration_dates=["2026-06-19", "2026-09-18"],
    )
    assert r.expiration_dates == ["2026-06-19", "2026-09-18"]


@pytest.mark.unit
def test_analyze_instrument_request_rejects_expiration_dates_for_equity() -> None:
    with pytest.raises(ValueError, match="expiration_dates is only supported"):
        AnalyzeInstrumentRequest(
            symbol="AAPL",
            market_type=MarketType.EQUITY,
            mode=AnalyzeMode.DETERMINISTIC,
            expiration_dates=["2026-06-19"],
            option_side=OptionSide.ALL,
        )
