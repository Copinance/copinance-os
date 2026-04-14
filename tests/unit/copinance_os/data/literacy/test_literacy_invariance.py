from __future__ import annotations

import re

import pytest

from copinance_os.data.literacy import instrument_analysis as ia_lit
from copinance_os.data.literacy import options_positioning as op_lit
from copinance_os.domain.models.profile import FinancialLiteracy

_ACRONYM_RE = re.compile(r"\b[A-Z]{2,}\b")


@pytest.mark.unit
def test_beginner_copy_avoids_acronym_leaks() -> None:
    beginner = FinancialLiteracy.BEGINNER
    texts = [
        ia_lit.equity_label_pe(beginner),
        ia_lit.equity_label_roe(beginner),
        ia_lit.options_label_avg_iv(beginner),
        op_lit.expl_implied_move(beginner, {"dte": 7, "annualized_iv": 24.2}),
        op_lit.expl_net_delta_exposure(beginner),
    ]
    assert all(_ACRONYM_RE.search(t) is None for t in texts)


@pytest.mark.unit
def test_tiered_copy_changes_across_literacy_levels() -> None:
    beginner = FinancialLiteracy.BEGINNER
    intermediate = FinancialLiteracy.INTERMEDIATE
    advanced = FinancialLiteracy.ADVANCED
    tiers = [
        (
            op_lit.name_net_gamma(beginner),
            op_lit.name_net_gamma(intermediate),
            op_lit.name_net_gamma(advanced),
        ),
        (
            op_lit.expl_pin_risk(beginner, {"pin_risk_level": "medium", "dte": 3}),
            op_lit.expl_pin_risk(intermediate, {"pin_risk_level": "medium", "dte": 3}),
            op_lit.expl_pin_risk(advanced, {"pin_risk_level": "medium", "dte": 3}),
        ),
    ]
    for b, i, a in tiers:
        assert len({b, i, a}) >= 2
