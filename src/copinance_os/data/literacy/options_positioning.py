"""Tiered narratives for aggregate options positioning.

Used by ``copinance_os.data.analytics.options.positioning`` (``build_options_positioning``).
Intermediate strings match the historical default so fixtures stay stable when literacy is omitted.
See ``copinance_os.domain.literacy`` for shared primitives and job-context normalization.

Research touchpoints (methodology, not forecasts): Bollen & Whaley (2004); Pan & Poteshman (2006);
SqueezeMetrics-style dealer gamma / Knuteson (2021, arXiv:2006.00975); Lakonishok, Lee & Poteshman
(2007) and standard OCC-style delta exposure; Brenner & Subrahmanyam (1988); Carr & Wu (2009);
Bates (2000).
"""

from __future__ import annotations

from typing import Any

from copinance_os.domain.literacy import TieredCopy
from copinance_os.domain.models.profile import FinancialLiteracy

# --- Positioning block (main four signals) ---

_TC_CALL_OI_SHARE_NAME = TieredCopy(
    beginner="Calls as a share of all contracts",
    intermediate="Call Open Interest Share",
    advanced="Call OI share",
)
_TC_CALL_OI_SHARE_EXPL = TieredCopy(
    beginner=(
        "Out of all option contracts that are open, this is the fraction that are calls. "
        "A higher share often means more people are positioned for the stock to go up."
    ),
    intermediate=(
        "A larger share of call OI points to aggregate upside interest "
        "in the chain — sometimes consistent with sizable call interest, "
        "but not exclusive to any one player."
    ),
    advanced="Elevated call-OI share vs total OI: upside positioning in aggregate; not a named holder read.",
)

_TC_PUT_CALL_OI_NAME = TieredCopy(
    beginner="Puts compared to calls (open contracts)",
    intermediate="Put/Call OI Ratio",
    advanced="Put/call OI",
)
_TC_PUT_CALL_OI_EXPL = TieredCopy(
    beginner=(
        "This compares how many put contracts are open to how many call contracts are open. "
        "A higher number can mean more people are buying protection against a drop."
    ),
    intermediate="Elevated put/call OI can indicate hedging pressure or defensive positioning.",
    advanced="Put/call OI >1: defensive skew or hedging demand vs calls; contrarian read context-dependent.",
)

_TC_FLOW_CALLS_NAME = TieredCopy(
    beginner="Today’s trading: share that is calls",
    intermediate="Intraday Options Flow (Calls Share)",
    advanced="Volume: calls share",
)
_TC_FLOW_CALLS_EXPL = TieredCopy(
    beginner=(
        "Of all option trades today, this is the share that were call trades. "
        "More call trading can mean short-term optimism."
    ),
    intermediate="Call-heavy volume relative to puts may indicate bullish tactical flow.",
    advanced="Call-heavy tape vs puts: tactical flow skew; not positioning stock.",
)

_TC_GAMMA_TILT_NAME = TieredCopy(
    beginner="Gamma tilt (how call vs put sensitivity balances)",
    intermediate="Gamma Tilt",
    advanced="Gamma tilt",
)
_TC_GAMMA_TILT_EXPL = TieredCopy(
    beginner=(
        "Gamma measures how fast an option’s sensitivity to price moves changes. "
        "Here we compare that effect between calls and puts using open contracts."
    ),
    intermediate="Positive gamma tilt can support stabilization and upside continuation.",
    advanced="Net gamma tilt from OI-weighted chain gammas; stabilization vs convexity amplifier read.",
)

_TC_DOLLAR_FLOW_NAME = TieredCopy(
    beginner="Big-dollar share of today’s option trading that is calls",
    intermediate="Dollar Call Flow Share",
    advanced="Dollar-weighted call volume share",
)
_TC_DOLLAR_FLOW_EXPL = TieredCopy(
    beginner=(
        "Instead of counting trades, we weight each trade by about how much money moved "
        "(price times size). That helps big trades count more than tiny ones."
    ),
    intermediate=(
        "Dollar call volume ÷ total dollar volume — economic magnitude of flow, "
        "not just contract counts (Bollen & Whaley 2004; Pan & Poteshman 2006)."
    ),
    advanced=(
        "Σ(mid·call vol·100) / Σ(mid·total vol·100); aligns with net buying pressure / "
        "information-in-volume literature (Bollen & Whaley 2004; Pan & Poteshman 2006)."
    ),
)

_TC_DOLLAR_PC_OI_NAME = TieredCopy(
    beginner="Put dollars vs call dollars still open",
    intermediate="Dollar Put/Call Open Interest",
    advanced="Dollar put OI / dollar call OI",
)
_TC_DOLLAR_PC_OI_EXPL = TieredCopy(
    beginner=(
        "This compares the dollar size of open put positions to open call positions. "
        "It treats expensive contracts as more important than very cheap ones."
    ),
    intermediate=(
        "Dollar-weighted put/call OI ratio — magnitude-weighted positioning vs simple counts "
        "(Bollen & Whaley 2004; Pan & Poteshman 2006)."
    ),
    advanced=(
        "Σ(mid·put OI·100) / Σ(mid·call OI·100); economic OI skew per classic option-volume "
        "information studies (Bollen & Whaley 2004; Pan & Poteshman 2006)."
    ),
)

# --- Volatility ---

_TC_ATM_IV_NAME = TieredCopy(
    beginner="Expected price swings at the current stock price (nearest expiry)",
    intermediate="ATM Implied Volatility",
    advanced="ATM IV (near)",
)
_TC_ATM_IV_MAIN = TieredCopy(
    beginner=(
        "This is the market’s best guess of how much the stock might move, annualized, "
        "for options whose strike is closest to today’s price, for the nearest expiration date."
    ),
    intermediate=(
        "At-the-money implied volatility for the nearest listed expiration — "
        "the market’s baseline fear / demand for premium at spot."
    ),
    advanced="Near-tenor ATM IV: baseline vol level at spot; fear/greed proxy.",
)

_TC_IV_RANK_NAME = TieredCopy(
    beginner="How high today’s “expected swing” is vs this whole list",
    intermediate="Intra-Chain IV Rank",
    advanced="IV rank (chain)",
)
_TC_IV_RANK_MAIN = TieredCopy(
    beginner=(
        "If this number is high, today’s expected swing at the money is high compared with "
        "other strikes in the same snapshot (0 = lowest, 1 = highest)."
    ),
    intermediate=(
        "Percentile of ATM IV versus all implied volatilities observed in this chain snapshot "
        "(0 = lowest, 1 = highest)."
    ),
    advanced="ATM IV percentile vs chain IV sample; cross-sectional rank only.",
)
_TC_IV_RANK_NO_IV = TieredCopy(
    beginner="We could not rank swings because there is not enough volatility data in this list.",
    intermediate="IV rank unavailable without a usable volatility sample across the chain.",
    advanced="IV rank undefined: insufficient IV sample in snapshot.",
)
_TC_IV_INSUFFICIENT = TieredCopy(
    beginner="We do not have enough data here to estimate expected swings at the money.",
    intermediate="Insufficient chain or spot data to estimate ATM implied volatility.",
    advanced="ATM IV unavailable: chain/spot insufficient.",
)
_TC_IV_NO_QUOTES = TieredCopy(
    beginner="There is no usable “expected swing” number near the stock price for this date.",
    intermediate="No quoted implied volatility near the money for the nearest expiration.",
    advanced="No ATM IV quotes near spot for front expiry.",
)
_TC_IV_RANK_DEGENERATE = TieredCopy(
    beginner="How today’s at-the-money swing compares with all other swing numbers in this list.",
    intermediate="How current ATM IV ranks versus all IV prints in this chain snapshot.",
    advanced="ATM IV cross-sectional rank vs chain IV prints.",
)

_TC_VOL_COMBO_NAME = TieredCopy(
    beginner="At-the-money swing and its rank in this list",
    intermediate="ATM Implied Volatility · IV Rank",
    advanced="ATM IV · IV rank",
)

# --- Surface ---

_TC_SKEW_INSUFFICIENT = TieredCopy(
    beginner="We could not compare “similar-risk” puts and calls because delta numbers are missing.",
    intermediate="Not enough delta quotes to estimate 25-delta skew for the nearest expiration.",
    advanced="25Δ skew undefined: insufficient delta quotes.",
)
_TC_SKEW_OK = TieredCopy(
    beginner=(
        "We compare expected swings on a put and a call chosen to react similarly to small price moves. "
        "If puts look more “expensive” than calls, people may be paying extra for protection."
    ),
    intermediate=(
        "IV of the ~25-delta put minus the ~25-delta call (nearest expiry). "
        "Positive skew often reflects downside protection demand. "
        "Wing richness (butterfly) and 10Δ skew extend the surface read (Carr & Wu 2009; Bates 2000)."
    ),
    advanced=(
        "25Δ risk-reversal skew (put IV − call IV, near); positive → downside protection bid. "
        "Butterfly vs ATM isolates wing richness (Carr & Wu 2009); crash-skew narratives (Bates 2000)."
    ),
)
_TC_TERM_NEED_TWO = TieredCopy(
    beginner="We need two dates with good data to compare expected swings over time.",
    intermediate="Need two expirations with ATM IV to infer term structure.",
    advanced="Term structure undefined: need two ATM IV slices.",
)

_TC_SKEW_25D_NAME = TieredCopy(
    beginner="Put vs call “expensive” tilt (similar-risk options)",
    intermediate="25-Delta Skew",
    advanced="25Δ skew",
)
_TC_TERM_STRUCTURE_NAME = TieredCopy(
    beginner="How expected swings compare across dates",
    intermediate="Term Structure",
    advanced="IV term structure",
)

# --- Flow ---

_TC_UNUSUAL_NAME = TieredCopy(
    beginner="Unusual trading score",
    intermediate="Unusual Activity Score",
    advanced="Unusual activity score",
)

_TC_AGG_VOL_OI_NAME = TieredCopy(
    beginner="All trading today vs all open contracts",
    intermediate="Aggregate Volume / OI",
    advanced="Agg vol / OI",
)
_TC_AGG_VOL_OI_EXPL = TieredCopy(
    beginner=(
        "This divides all option trades today by all contracts still open. A higher number can "
        "mean more people are actively trading compared with positions that are just sitting there."
    ),
    intermediate=(
        "Total options volume divided by total open interest — higher values can "
        "indicate more tactical trading versus stuck inventory."
    ),
    advanced="Chain vol/OI: turnover vs inventory; tactical flow proxy.",
)

# --- Gamma ---

_TC_NET_GAMMA_EXPL = TieredCopy(
    beginner=(
        "This adds up how much “speed of change” exposure calls have, minus puts, using open "
        "contracts and today’s stock price. It is a rough picture, not a precise bank report."
    ),
    intermediate="Sum of gamma × OI × 100 × spot for calls minus puts — a coarse dealer-gamma proxy.",
    advanced="Dealer-gamma proxy: Σ(call γ·OI·100·S) − Σ(put γ·OI·100·S); sign = net inventory convexity.",
)
_TC_NET_GAMMA_NAME = TieredCopy(
    beginner="Net “speed-of-change” exposure (calls minus puts)",
    intermediate="Net Gamma Exposure",
    advanced="Net gamma (OI-weighted)",
)
_TC_GAMMA_REGIME_NAME = TieredCopy(
    beginner="Gamma regime (stabilizing vs amplifying)",
    intermediate="Gamma Regime",
    advanced="Gamma regime",
)
_TC_GAMMA_NEUTRAL = TieredCopy(
    beginner="Gamma effects look tiny in this snapshot, so we label the regime neutral.",
    intermediate="Gamma exposure is negligible in this snapshot — regime is effectively neutral.",
    advanced="Net |γ·OI| negligible → neutral gamma regime.",
)
_TC_GAMMA_POS = TieredCopy(
    beginner=(
        "If this pattern held, option dealers might tend to lean against big price spikes and dips, "
        "which can calm day-to-day moves."
    ),
    intermediate=(
        "Net gamma is positive — dealers are more likely to stabilize moves "
        "(fade extremes) if this positioning persists."
    ),
    advanced="Net dealer gamma >0: stabilization / mean-reversion pressure if inventory persists.",
)
_TC_GAMMA_NEG = TieredCopy(
    beginner="If this pattern held, option hedging could sometimes add fuel to strong trends.",
    intermediate=(
        "Net gamma is negative — convexity can amplify moves as hedgers chase delta "
        "in trending conditions."
    ),
    advanced="Net dealer gamma <0: convexity supply; trend amplification risk under chase.",
)
_TC_GAMMA_BAL = TieredCopy(
    beginner="Calls and puts balance out so we do not label a strong stabilizing or amplifying regime.",
    intermediate="Gamma is balanced — neither strong stabilization nor strong convexity amplification.",
    advanced="Balanced net gamma: no dominant stabilization vs convexity regime.",
)

_TC_GAMMA_FLIP_NAME = TieredCopy(
    beginner="Price level where net “speed-of-change” exposure from options flips sign",
    intermediate="Gamma Flip Strike (nearest expiry)",
    advanced="Gamma flip (dealer GEX zero-cross, near)",
)
_TC_GAMMA_FLIP_EXPL = TieredCopy(
    beginner=(
        "This is a price people watch from the options list: where hedging math suggests the "
        "market’s push-and-pull from options might switch styles."
    ),
    intermediate=(
        "Strike where cumulative per-strike GEX (calls − puts, OI-weighted, ×100×spot) crosses zero "
        "on the front expiry — a common “flip” narrative (SqueezeMetrics-style dealer gamma; "
        "Knuteson 2021, arXiv:2006.00975)."
    ),
    advanced=(
        "Zero-cross of Σ_K (call γ·OI − put γ·OI)·100·S on ascending strikes; institutional "
        "dealer-gamma flip read (cf. SqueezeMetrics; Knuteson 2021, arXiv:2006.00975)."
    ),
)

_TC_NET_DELTA_NAME = TieredCopy(
    beginner="Directional “push” implied by open options (very simplified)",
    intermediate="Net Delta Exposure (DEX)",
    advanced="Net delta × OI × 100 (chain)",
)
_TC_NET_DELTA_EXPL = TieredCopy(
    beginner=(
        "Delta is how much an option’s price might move when the stock moves a little. "
        "Here we add that up across open contracts to get a rough directional picture."
    ),
    intermediate=(
        "Sum of delta × open interest × 100 (calls + puts) — aggregate directional exposure "
        "in the chain (Lakonishok, Lee & Poteshman 2007; OCC/CBOE-style positioning summaries)."
    ),
    advanced=(
        "DEX: Σ δ·OI·100; dollar_delta = DEX·S. Standard positioning statistic "
        "(Lakonishok, Lee & Poteshman 2007; exchange/OCC reporting analogues)."
    ),
)

# --- Structure ---

_TC_MAX_PAIN_NAME = TieredCopy(
    beginner="Price where option payouts might be lowest (simple story)",
    intermediate="Max Pain Strike",
    advanced="Max pain (nearest)",
)
_TC_MAX_PAIN_EXPL = TieredCopy(
    beginner=(
        "This is the price, for the nearest date, where total option payouts if the stock closed "
        "there would be as small as possible in this simple model. It is a common story people tell; "
        "it is not a forecast."
    ),
    intermediate=(
        "Strike that minimizes total intrinsic value paid to option holders at expiration "
        "(nearest expiry only) — a common magnet narrative, not a forecast."
    ),
    advanced="Nearest-expiry max-pain strike (intrinsic minimizer); narrative magnet, not a forecast.",
)

_TC_STRIKE_MAGNETS_NAME = TieredCopy(
    beginner="Prices where the most contracts are open (nearest date)",
    intermediate="Strike Magnets (OI)",
    advanced="OI magnets (near)",
)
_TC_STRIKE_MAGNETS_EXPL = TieredCopy(
    beginner=(
        "These are the stock prices where the largest number of option contracts are open for the "
        "nearest date — places traders often watch."
    ),
    intermediate="Largest open-interest strikes in the nearest expiration — where inventory tends to cluster.",
    advanced="Top OI strikes (front expiry): inventory clustering / potential pin context.",
)

_TC_IMPL_MOVE_NAME = TieredCopy(
    beginner="Rough “expected one-day move” from option prices (nearest date)",
    intermediate="Implied Move (Straddle)",
    advanced="Implied move (ATM straddle)",
)
_TC_IMPL_MOVE_EXPL = TieredCopy(
    beginner=(
        "We average the prices of the nearest call and put at the stock price, add them, and "
        "compare to the stock price to get a simple percent move people talk about."
    ),
    intermediate=(
        "ATM straddle mid / spot for the nearest expiration — a rough implied move proxy; "
        "when DTE is available we also show Brenner & Subrahmanyam (1988) σ from the straddle "
        "and DTE-consistent daily/period moves."
    ),
    advanced=(
        "Raw straddle/spot plus Brenner–Subrahmanyam (1988) σ ≈ straddle / (0.798·S·√(T)); "
        "daily = σ/√252, horizon = σ√(DTE/252). Crude; not a realized-vol forecast."
    ),
)

_TC_VANNA_NAME = TieredCopy(
    beginner="Vanna exposure (hedging vs swing expectations)",
    intermediate="Vanna Exposure",
    advanced="Net vanna (OI-weighted)",
)
_TC_VANNA_EXPL = TieredCopy(
    beginner=(
        "How sensitive overall option hedging is to changes in expected price swings. "
        "If this is very negative, a spike in expected swings could push the stock down faster."
    ),
    intermediate=(
        "Net vanna exposure — when negative, rising IV forces dealers to sell delta, "
        "amplifying downside moves. When positive, IV spikes trigger buying."
    ),
    advanced=(
        "Net vanna (∂²V/∂S∂σ × OI): short vanna → vol-up-spot-down dynamic; "
        "regime from OI-weighted aggregate (Bergomi smile dynamics; dealer hedging flows)."
    ),
)

_TC_CHARM_NAME = TieredCopy(
    beginner="Overnight hedging drift (charm)",
    intermediate="Charm Exposure",
    advanced="Net charm (OI-weighted)",
)
_TC_CHARM_EXPL = TieredCopy(
    beginner="How much the hedging balance shifts overnight just from time passing.",
    intermediate=(
        "OI-weighted charm (∂Δ/∂T): positive net charm often means delta drifts up with time, "
        "so dealers may lean into selling at the open (overnight drift)."
    ),
    advanced=(
        "Charm exposure: OI-weighted ∂Δ/∂T; positive → dealer delta accretion overnight → "
        "selling pressure into the open (Taleb, Dynamic Hedging; dealer theta drift)."
    ),
)

_TC_MISPRICING_NAME = TieredCopy(
    beginner="Model vs market option prices",
    intermediate="BSM Mispricing Sentiment",
    advanced="BSM mid vs NPV (sentiment)",
)
_TC_MISPRICING_EXPL = TieredCopy(
    beginner="Whether option prices look high or low versus a simple fair-value model.",
    intermediate=(
        "Average mid vs Black–Scholes NPV by side — persistent call richness can signal "
        "demand not fully priced through IV alone."
    ),
    advanced=(
        "BSM mid − NPV / NPV (%): systematic mispricing vs analytic European price "
        "(De Fontnouvelle et al. 2003-style sentiment read; not a pure arb)."
    ),
)

_TC_MONEYNESS_FLOW_NAME = TieredCopy(
    beginner="Where trading clusters by moneyness",
    intermediate="Dominant Flow Moneyness",
    advanced="Delta-bucketed dominant flow",
)
_TC_MONEYNESS_FLOW_EXPL = TieredCopy(
    beginner=(
        "Where most of the option trading is happening — at the current price, above it, "
        "or far above/below it."
    ),
    intermediate=(
        "Delta-bucketed open interest and dollar volume — shows whether flow concentrates "
        "at the money or in wings."
    ),
    advanced=(
        "Delta-bucketed flow decomposition: dominant bucket flags speculative vs hedging "
        "activity by moneyness (OCC-style surface splits; Lakonishok et al. 2007 context)."
    ),
)

_TC_PIN_RISK_NAME = TieredCopy(
    beginner="Expiry pin risk",
    intermediate="Pin Risk",
    advanced="Near-expiry pin (OI × P(ITM))",
)
_TC_PIN_RISK_EXPL = TieredCopy(
    beginner=(
        "When options are about to expire, the stock price sometimes gets ‘stuck’ near a price "
        "where a lot of contracts are open. This measures that risk."
    ),
    intermediate=(
        "Near-expiry pin risk from OI-weighted risk-neutral P(ITM) × strike concentration "
        "versus recent volume."
    ),
    advanced=(
        "Pin risk from OI × P(ITM) at high-OI strikes (QuantLib itmCashProbability); "
        "Avellaneda–Lipkin (2003) dealer re-hedging / pinning mechanism."
    ),
)


def analyst_summary(
    symbol: str, bias: str, confidence: float, window: str, lit: FinancialLiteracy
) -> str:
    horizon_b = "the next week or two" if window == "near" else "the next month or two"
    horizon_i = "next 1-2 weeks" if window == "near" else "next 1-2 months"
    horizon_a = "front slice" if window == "near" else "mid horizon"

    if bias == "bullish":
        tone_b = (
            f"For {symbol}, more option contracts and trading lean toward people expecting the "
            "price to rise than fall, when you add up the whole list of strikes. "
            "That is a big-picture picture of the market, not a story about one investor."
        )
        tone_i = "the aggregate options surface leans bullish — more call-heavy OI and flow"
        tone_a = "aggregate positioning reads call-heavy on OI and flow; surface bias bullish"
    elif bias == "bearish":
        tone_b = (
            f"For {symbol}, more option activity points to people protecting against a drop "
            "or betting on a drop, when you look at the whole chain together."
        )
        tone_i = (
            "the aggregate options surface leans bearish — more defensive put weight "
            "or softer call demand"
        )
        tone_a = "surface skews defensive: put weight or weak call demand dominates aggregates"
    else:
        tone_b = (
            f"For {symbol}, the mix of call and put contracts does not clearly favor one direction "
            "in this snapshot."
        )
        tone_i = "the options surface is mixed — no strong one-sided aggregate skew yet"
        tone_a = "no clear one-sided aggregate skew; balanced positioning reads"

    tail_b = (
        f" We do not name specific funds. This read is about {confidence * 100:.0f}% confident "
        f"for {horizon_b}, in plain language."
    )
    tail_i = (
        " That reflects overall market positioning in the chain, "
        "not a specific actor; heavy clusters can sometimes line up with large books, "
        "but we do not label institutions. "
        f"Model confidence is {confidence * 100:.0f}% for the {horizon_i} horizon."
    )
    tail_a = f" Confidence {confidence:.2f} ({horizon_a}); clusters are inventory, not named flow."

    if lit == FinancialLiteracy.BEGINNER:
        return tone_b + tail_b
    if lit == FinancialLiteracy.ADVANCED:
        return f"{symbol}: {tone_a}.{tail_a}"
    return f"For {symbol}, {tone_i}.{tail_i}"


def scenario_narratives(symbol: str, lit: FinancialLiteracy) -> tuple[str, str, str]:
    bull = TieredCopy(
        beginner=(
            f"If {symbol} stays above the price levels where a lot of contracts sit, the uptrend "
            "could continue."
        ),
        intermediate=f"Upside continuation if {symbol} holds above option-supported levels.",
        advanced=(
            f"Continuation bias if spot holds above OI clusters / short-gamma strikes in {symbol}."
        ),
    )
    bear = TieredCopy(
        beginner=(
            f"If more people buy protection or unwind bullish trades, {symbol} could see more "
            "downward pressure."
        ),
        intermediate=f"Downside pressure if hedging demand rises and calls unwind in {symbol}.",
        advanced=f"Drawdown risk if hedging lifts and call inventory unwinds in {symbol}.",
    )
    range_tc = TieredCopy(
        beginner="Prices may bounce in a range if buyers and sellers stay evenly matched.",
        intermediate="Mean-reverting regime likely if neither side gains flow dominance.",
        advanced="Range regime if flow does not break to one side; gamma pin possible.",
    )
    return bull.pick(lit), bear.pick(lit), range_tc.pick(lit)


def name_call_oi_share(lit: FinancialLiteracy) -> str:
    return _TC_CALL_OI_SHARE_NAME.pick(lit)


def expl_call_oi_share(lit: FinancialLiteracy) -> str:
    return _TC_CALL_OI_SHARE_EXPL.pick(lit)


def name_put_call_oi(lit: FinancialLiteracy) -> str:
    return _TC_PUT_CALL_OI_NAME.pick(lit)


def expl_put_call_oi(lit: FinancialLiteracy) -> str:
    return _TC_PUT_CALL_OI_EXPL.pick(lit)


def name_flow_calls_share(lit: FinancialLiteracy) -> str:
    return _TC_FLOW_CALLS_NAME.pick(lit)


def expl_flow_calls_share(lit: FinancialLiteracy) -> str:
    return _TC_FLOW_CALLS_EXPL.pick(lit)


def name_gamma_tilt(lit: FinancialLiteracy) -> str:
    return _TC_GAMMA_TILT_NAME.pick(lit)


def expl_gamma_tilt(lit: FinancialLiteracy) -> str:
    return _TC_GAMMA_TILT_EXPL.pick(lit)


def name_atm_iv(lit: FinancialLiteracy) -> str:
    return _TC_ATM_IV_NAME.pick(lit)


def expl_atm_iv_main(lit: FinancialLiteracy) -> str:
    return _TC_ATM_IV_MAIN.pick(lit)


def name_iv_rank(lit: FinancialLiteracy) -> str:
    return _TC_IV_RANK_NAME.pick(lit)


def expl_iv_rank_main(lit: FinancialLiteracy) -> str:
    return _TC_IV_RANK_MAIN.pick(lit)


def expl_iv_rank_no_iv(lit: FinancialLiteracy) -> str:
    return _TC_IV_RANK_NO_IV.pick(lit)


def expl_iv_insufficient(lit: FinancialLiteracy) -> str:
    return _TC_IV_INSUFFICIENT.pick(lit)


def expl_iv_no_quotes_near_money(lit: FinancialLiteracy) -> str:
    return _TC_IV_NO_QUOTES.pick(lit)


def expl_iv_rank_degenerate(lit: FinancialLiteracy) -> str:
    return _TC_IV_RANK_DEGENERATE.pick(lit)


def name_vol_combo_atm_iv_rank(lit: FinancialLiteracy) -> str:
    return _TC_VOL_COMBO_NAME.pick(lit)


def expl_vol_combo(lit: FinancialLiteracy, atm_val: float, iv_rank_val: float) -> str:
    return TieredCopy(
        beginner=(
            f"The market’s “expected swing” at the stock price is about {atm_val:.2f} percent per year "
            f"(shown as a percent number). Compared with all other strikes here, that ranks about "
            f"{iv_rank_val:.0%} of the way from lowest to highest."
        ),
        intermediate=(
            f"ATM IV is {atm_val:.2f}% (percentage points). "
            f"Intra-chain IV rank {iv_rank_val:.0%} — how that ATM print ranks versus "
            f"all implied volatilities in this snapshot."
        ),
        advanced=(
            f"ATM IV {atm_val:.2f}%; intra-chain IV rank {iv_rank_val:.0%} vs snapshot IV sample."
        ),
    ).pick(lit)


def expl_skew_insufficient(lit: FinancialLiteracy) -> str:
    return _TC_SKEW_INSUFFICIENT.pick(lit)


def expl_skew_ok(lit: FinancialLiteracy) -> str:
    return _TC_SKEW_OK.pick(lit)


def expl_term_need_two(lit: FinancialLiteracy) -> str:
    return _TC_TERM_NEED_TWO.pick(lit)


def name_skew_25d(lit: FinancialLiteracy) -> str:
    return _TC_SKEW_25D_NAME.pick(lit)


def name_term_structure(lit: FinancialLiteracy) -> str:
    return _TC_TERM_STRUCTURE_NAME.pick(lit)


def expl_term_move(lit: FinancialLiteracy, near: float, far: float, slope: str) -> str:
    label_b = slope.replace("_", " ")
    return TieredCopy(
        beginner=(
            f"Expected swings at the stock price go from about {near:.1f}% to about {far:.1f}% "
            f"when you move to the next date we can compare — that pattern is called {label_b} here."
        ),
        intermediate=f"ATM IV moves from {near:.1f}% (near) to {far:.1f}% (next slice) — {label_b}.",
        advanced=f"ATM IV {near:.1f}% → {far:.1f}% (next); {slope}.",
    ).pick(lit)


def name_unusual_activity(lit: FinancialLiteracy) -> str:
    return _TC_UNUSUAL_NAME.pick(lit)


def expl_unusual_activity(lit: FinancialLiteracy, vol_threshold: int) -> str:
    return TieredCopy(
        beginner=(
            f"We count places where today’s trading is unusually high compared with contracts still open "
            f"(more than twice as much trading as open contracts, and more than {vol_threshold} trades), "
            "then turn that into a 0–100 style score."
        ),
        intermediate=(
            f"Counts strikes where volume is elevated versus open interest (ratio > 2, "
            f"volume > {vol_threshold}), scaled into a 0–100-style intensity score."
        ),
        advanced=(
            f"Heuristic unusual-activity score: vol/OI>2 & vol>{vol_threshold} strikes, scaled 0–100."
        ),
    ).pick(lit)


def name_agg_vol_oi(lit: FinancialLiteracy) -> str:
    return _TC_AGG_VOL_OI_NAME.pick(lit)


def expl_agg_vol_oi(lit: FinancialLiteracy) -> str:
    return _TC_AGG_VOL_OI_EXPL.pick(lit)


def expl_net_gamma(lit: FinancialLiteracy) -> str:
    return _TC_NET_GAMMA_EXPL.pick(lit)


def name_net_gamma(lit: FinancialLiteracy) -> str:
    return _TC_NET_GAMMA_NAME.pick(lit)


def name_gamma_regime(lit: FinancialLiteracy) -> str:
    return _TC_GAMMA_REGIME_NAME.pick(lit)


def expl_gamma_neutral_flat(lit: FinancialLiteracy) -> str:
    return _TC_GAMMA_NEUTRAL.pick(lit)


def expl_gamma_positive(lit: FinancialLiteracy) -> str:
    return _TC_GAMMA_POS.pick(lit)


def expl_gamma_negative(lit: FinancialLiteracy) -> str:
    return _TC_GAMMA_NEG.pick(lit)


def expl_gamma_balanced(lit: FinancialLiteracy) -> str:
    return _TC_GAMMA_BAL.pick(lit)


def name_max_pain(lit: FinancialLiteracy) -> str:
    return _TC_MAX_PAIN_NAME.pick(lit)


def expl_max_pain(lit: FinancialLiteracy) -> str:
    return _TC_MAX_PAIN_EXPL.pick(lit)


def name_strike_magnets(lit: FinancialLiteracy) -> str:
    return _TC_STRIKE_MAGNETS_NAME.pick(lit)


def expl_strike_magnets(lit: FinancialLiteracy) -> str:
    return _TC_STRIKE_MAGNETS_EXPL.pick(lit)


def name_implied_move(lit: FinancialLiteracy) -> str:
    return _TC_IMPL_MOVE_NAME.pick(lit)


def expl_implied_move(
    lit: FinancialLiteracy, implied_move_detail: dict[str, Any] | None = None
) -> str:
    base = _TC_IMPL_MOVE_EXPL.pick(lit)
    if not implied_move_detail:
        return base
    dte = implied_move_detail.get("dte")
    ann = implied_move_detail.get("annualized_iv")
    daily = implied_move_detail.get("daily_implied_move_pct")
    period = implied_move_detail.get("period_implied_move_pct")
    if dte is None or ann is None:
        return base
    tail = TieredCopy(
        beginner=(
            f"For this slice: about {dte} calendar days to expiry; Brenner–Subrahmanyam-style σ "
            f"≈ {ann:.2f}% annualized."
        ),
        intermediate=(
            f"DTE={dte}, σ_BS88≈{ann:.2f}% ann.; daily≈{daily}%, horizon≈{period}% "
            "(see implied_move_detail)."
        ),
        advanced=(
            f"DTE={dte}; σ_BS88={ann:.4f}%; daily={daily}; period={period} (Brenner & Subrahmanyam 1988)."
        ),
    ).pick(lit)
    return f"{base} {tail}"


def name_dollar_call_flow_share(lit: FinancialLiteracy) -> str:
    return _TC_DOLLAR_FLOW_NAME.pick(lit)


def expl_dollar_call_flow_share(lit: FinancialLiteracy) -> str:
    return _TC_DOLLAR_FLOW_EXPL.pick(lit)


def name_dollar_put_call_oi(lit: FinancialLiteracy) -> str:
    return _TC_DOLLAR_PC_OI_NAME.pick(lit)


def expl_dollar_put_call_oi(lit: FinancialLiteracy) -> str:
    return _TC_DOLLAR_PC_OI_EXPL.pick(lit)


def name_gamma_flip_strike(lit: FinancialLiteracy) -> str:
    return _TC_GAMMA_FLIP_NAME.pick(lit)


def expl_gamma_flip_strike(
    lit: FinancialLiteracy, gamma_flip_strike: float | None, spot: float
) -> str:
    base = _TC_GAMMA_FLIP_EXPL.pick(lit)
    if gamma_flip_strike is None:
        tail = TieredCopy(
            beginner=" In this snapshot we did not find a clear flip level.",
            intermediate=" No cumulative GEX sign change on the front expiry — flip strike unset.",
            advanced=" No GEX zero-cross in sorted strikes (insufficient gamma/OI structure).",
        ).pick(lit)
        return f"{base}{tail}"
    tail = TieredCopy(
        beginner=f" Estimated flip near {gamma_flip_strike:.2f} vs spot about {spot:.2f}.",
        intermediate=f" Interpolated flip ≈ {gamma_flip_strike:.2f} (spot {spot:.2f}).",
        advanced=f" Flip≈{gamma_flip_strike:.4f} vs S={spot:.4f}.",
    ).pick(lit)
    return f"{base} {tail}"


def name_net_delta_exposure(lit: FinancialLiteracy) -> str:
    return _TC_NET_DELTA_NAME.pick(lit)


def expl_net_delta_exposure(lit: FinancialLiteracy) -> str:
    return _TC_NET_DELTA_EXPL.pick(lit)


def name_vanna_exposure(lit: FinancialLiteracy) -> str:
    return _TC_VANNA_NAME.pick(lit)


def expl_vanna_exposure(lit: FinancialLiteracy, regime: str) -> str:
    base = _TC_VANNA_EXPL.pick(lit)
    tail = TieredCopy(
        beginner=f" Regime here reads as {regime.replace('_', ' ')}.",
        intermediate=f" Classified regime: {regime}.",
        advanced=f" Regime={regime} (thresholded net vanna).",
    ).pick(lit)
    return f"{base}{tail}"


def name_charm_exposure(lit: FinancialLiteracy) -> str:
    return _TC_CHARM_NAME.pick(lit)


def expl_charm_exposure(lit: FinancialLiteracy, drift: str) -> str:
    base = _TC_CHARM_EXPL.pick(lit)
    tail = TieredCopy(
        beginner=f" Overnight drift label: {drift.replace('_', ' ')}.",
        intermediate=f" Overnight delta drift: {drift}.",
        advanced=f" Drift={drift}.",
    ).pick(lit)
    return f"{base}{tail}"


def name_bsm_mispricing(lit: FinancialLiteracy) -> str:
    return _TC_MISPRICING_NAME.pick(lit)


def expl_bsm_mispricing(
    lit: FinancialLiteracy, call_avg: float, put_avg: float, sentiment: str
) -> str:
    base = _TC_MISPRICING_EXPL.pick(lit)
    tail = TieredCopy(
        beginner=(
            f" Calls are about {call_avg:.2f}% vs model on average; puts about {put_avg:.2f}%. "
            f"Sentiment tag: {sentiment.replace('_', ' ')}."
        ),
        intermediate=(
            f" Avg call mispricing {call_avg:.2f}%, put {put_avg:.2f}% — sentiment {sentiment}."
        ),
        advanced=f" call_avg={call_avg:.4f}% put_avg={put_avg:.4f}% sentiment={sentiment}.",
    ).pick(lit)
    return f"{base} {tail}"


def name_dominant_flow_moneyness(lit: FinancialLiteracy) -> str:
    return _TC_MONEYNESS_FLOW_NAME.pick(lit)


def expl_dominant_flow_moneyness(
    lit: FinancialLiteracy, dominant_call: str | None, dominant_put: str | None
) -> str:
    base = _TC_MONEYNESS_FLOW_EXPL.pick(lit)
    dc = dominant_call or "n/a"
    dp = dominant_put or "n/a"
    tail = TieredCopy(
        beginner=f" Most dollar call volume sits in the {dc} bucket; puts in {dp}.",
        intermediate=f" Dominant call bucket {dc}; dominant put bucket {dp} (delta bands).",
        advanced=f" dominant_call_bucket={dc} dominant_put_bucket={dp}.",
    ).pick(lit)
    return f"{base} {tail}"


def name_pin_risk(lit: FinancialLiteracy) -> str:
    return _TC_PIN_RISK_NAME.pick(lit)


def expl_pin_risk(lit: FinancialLiteracy, pin_bundle: dict[str, Any]) -> str:
    base = _TC_PIN_RISK_EXPL.pick(lit)
    lvl = pin_bundle.get("pin_risk_level", "low")
    mx = pin_bundle.get("max_pin_strike")
    dte = pin_bundle.get("dte")
    tail = TieredCopy(
        beginner=(
            f" Level {lvl}. "
            f"{f'Focus strike about {mx}.' if mx is not None else 'No single focus strike stood out.'} "
            f"{f'About {dte} days to expiry.' if dte is not None else ''}"
        ),
        intermediate=(
            f" Pin risk {lvl}; max pin strike {mx}; DTE {dte}."
            if mx is not None
            else f" Pin risk {lvl}; DTE {dte}."
        ),
        advanced=f" pin_risk_level={lvl} max_pin_strike={mx} dte={dte}.",
    ).pick(lit)
    return f"{base} {tail}"
