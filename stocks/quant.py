"""
Quantitative Analysis Engine — Unified Multi-Module Scoring System

Five sub-scores (each 0-100), then weighted composite:

  1. TECHNICAL (MACD, Stochastic, ATR, OBV, ADX, Fibonacci)
  2. STATISTICAL (Markov Chain, Kalman Filter, Hurst Exponent, Mean Reversion Z-score)
  3. ML TREND (Linear Regression, R², Velocity/Acceleration, Volatility Regime)
  4. RISK (Sharpe, Sortino, Max Drawdown, VaR, Beta, Correlation)
  5. FUNDAMENTAL (Multi-Factor: Value/Growth/Quality/Momentum, GARP/PEG)

Composite weights differ by asset type:
  Individual Stock: Tech 20% | Stat 25% | ML 15% | Risk 15% | Fund 25%
  ETF:             Tech 30% | Stat 30% | ML 20% | Risk 20% | Fund  0%
  Speculative/Gem: Tech 30% | Stat 30% | ML 20% | Risk 10% | Fund 10%
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional

from stocks.technical  import compute_technical_score, TechnicalScore
from stocks.risk_metrics import (
    compute_risk_metrics, compute_ml_trend, compute_volatility_regime,
    RiskMetrics, MLTrendSignal, VolatilityRegime
)


# ══════════════════════════════════════════════════════════════════════════════
# STATISTICAL SUB-MODULE (Markov, Kalman, Hurst, Mean Reversion)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MarkovAnalysis:
    """
    3-state Markov Chain: BULL / BEAR / SIDEWAYS.
    Built from 252 days of daily returns.

    How it works: classify each day → build 3×3 empirical transition matrix
    → given today's state, compute P(tomorrow = BULL/BEAR/SIDEWAYS).
    Chain 5 transitions → E[5-day return].

    State persistence > 0.6 = trending market (momentum works).
    State persistence < 0.45 = choppy market (mean reversion works).
    """
    current_state: str
    prob_bull_tomorrow: float
    prob_bear_tomorrow: float
    prob_sideways_tomorrow: float
    state_persistence: float        # P(stay in current state)
    expected_return_5d: float       # E[5-day return] in %
    regime_signal: str              # "TRENDING" | "CHOPPY"
    stat_score: float               # 0-100 contribution to statistical score


@dataclass
class KalmanState:
    """
    Kalman Filter: optimal linear state estimator (tracks 'true price' + trend).
    Originally from aerospace — Apollo used it for navigation.

    In finance: treat price as noisy signal around hidden fair value.
    Kalman Z-score = (price - Kalman_fair_value) / noise_std:
      Z < -1.0: price below fair value → potential upward reversion
      Z > +1.0: price above fair value → potentially overextended
    """
    filtered_price: float
    trend_velocity: float           # estimated daily drift (+ = uptrend)
    kalman_zscore: float            # deviation from Kalman fair value
    signal: str                     # "ABOVE_FAIR" | "BELOW_FAIR" | "FAIR"
    gain: float


@dataclass
class HurstResult:
    """
    Hurst Exponent via R/S analysis.
    H < 0.45: mean-reverting (use Z-score strategies, fade extremes)
    H = 0.50: random walk (no edge)
    H > 0.55: trending/persistent (use momentum strategies)
    """
    hurst: float
    interpretation: str             # "MEAN_REVERTING" | "RANDOM" | "TRENDING"
    strategy_fit: str
    confidence: str


@dataclass
class MeanReversionSignal:
    zscore_20d: float
    zscore_50d: float
    bollinger_pct: float
    is_oversold: bool
    is_overbought: bool
    signal_strength: float          # -1 to +1


@dataclass
class StatisticalScore:
    """All four statistical signals combined."""
    markov: MarkovAnalysis
    kalman: KalmanState
    hurst: HurstResult
    mean_reversion: MeanReversionSignal
    composite_score: float          # 0-100
    signal: str


@dataclass
class EntryQuality:
    """
    Entry-timing overlay — answers "should I buy TODAY or wait?".

    This is deliberately NOT folded into overall_quant_score (which ranks
    long-term value). It's a separate, descriptive timing layer that combines
    three already-computed signals:
      • MACD            — momentum DIRECTION (is the move up or down right now?)
      • Hurst           — momentum PERSISTENCE (is the trend real or will it revert?)
      • Bollinger %     — where price sits in its normal band (over-extended?)

    The key insight is the pairing: MACD-up + Hurst-trending = a *real* trend
    worth entering; MACD-up + Hurst-mean-reverting = *fake* momentum that will
    snap back, so don't chase. Bollinger is a confirmation filter, never a
    standalone signal — MACD-up but already through the upper band means "right
    idea, wrong price → wait for the pullback / use a limit order".
    """
    rating: str          # BUY_NOW | WAIT_PULLBACK | WATCH_BOUNCE | AVOID | NEUTRAL
    score: float         # 0-100 entry-timing quality (higher = better entry today)
    bb_position: float   # bollinger_pct: 0 = lower band, 0.5 = mid, 1 = upper band
    bb_flag: str         # OVERBOUGHT | OVERSOLD | NORMAL
    note: str            # one-line "buy today vs wait" rationale


@dataclass
class FundamentalScore:
    """
    Multi-factor fundamental model (Value/Growth/Quality/Momentum).
    Weights: Value 25% | Growth 30% | Quality 25% | Momentum 20%.
    PEG = PE / earnings_growth_rate (<1 = cheap for growth, GARP ideal).

    The Quality leg is an AQR "Quality Minus Junk" (Asness-Frazzini-Pedersen 2019)
    composite of three pillars, each 0-10 — exposed below so the thesis can name
    *why* a name scores as quality (or junk):
      qmj_profitability — net margin + ROE (does it earn high returns on capital?)
      qmj_growth        — prior growth in earnings & revenue (is quality rising?)
      qmj_safety        — low leverage + positive, stable earnings (will it survive?)
    """
    value_score: float
    growth_score: float
    quality_score: float
    momentum_score: float
    composite_score: float          # 0-10
    peg_ratio: Optional[float]
    garp_rating: str
    # QMJ Quality pillars (0-10 each); default None for back-compat construction.
    qmj_profitability: Optional[float] = None
    qmj_growth: Optional[float] = None
    qmj_safety: Optional[float] = None


@dataclass
class QuantReport:
    """
    Full quantitative report with five sub-scores + composite.
    This is the main output used by all screeners and the AI analyst.
    """
    ticker: str
    # ── Sub-scores (each 0-100) ──
    technical: TechnicalScore
    statistical: StatisticalScore
    ml_trend: MLTrendSignal
    vol_regime: VolatilityRegime
    risk: RiskMetrics
    fundamental: FundamentalScore
    # ── Composite ──
    overall_quant_score: float      # 0-100
    signal_type: str                # STRONG_BUY | BUY | HOLD | SELL | STRONG_SELL
    quant_thesis: str
    signal_conflicts: str = ""      # human-readable note when factors disagree
    # Entry-timing overlay (defaults to None for back-compat construction in tests)
    entry_quality: Optional["EntryQuality"] = None
    # ── Convenience shortcuts ──
    @property
    def momentum(self): return self.technical.macd  # backward compat
    @property
    def mean_reversion(self): return self.statistical.mean_reversion
    @property
    def markov(self): return self.statistical.markov
    @property
    def kalman(self): return self.statistical.kalman
    @property
    def hurst(self): return self.statistical.hurst
    @property
    def factors(self): return self.fundamental
    @property
    def entry(self): return self.entry_quality


# ══════════════════════════════════════════════════════════════════════════════
# STATISTICAL IMPLEMENTATIONS
# ══════════════════════════════════════════════════════════════════════════════

def _classify_state(ret: float) -> str:
    if ret > 0.005: return "BULL"
    if ret < -0.005: return "BEAR"
    return "SIDEWAYS"


def _compute_markov(closes: pd.Series) -> MarkovAnalysis:
    rets   = closes.pct_change().dropna().tail(252)
    states = [_classify_state(float(r)) for r in rets]
    labels = ["BULL", "BEAR", "SIDEWAYS"]
    sr     = {"BULL": 0.008, "BEAR": -0.008, "SIDEWAYS": 0.0005}

    counts = {s: {t: 0 for t in labels} for s in labels}
    for i in range(len(states) - 1):
        counts[states[i]][states[i+1]] += 1

    trans = {}
    for s in labels:
        total = sum(counts[s].values()) or 1
        trans[s] = {t: counts[s][t] / total for t in labels}

    cur = states[-1]
    p   = trans[cur]
    sv  = np.array([p["BULL"], p["SIDEWAYS"], p["BEAR"]])
    rv  = np.array([sr["BULL"], sr["SIDEWAYS"], sr["BEAR"]])
    exp5d = round(((1 + float(np.dot(sv, rv)))**5 - 1) * 100, 2)

    persistence = trans[cur][cur]
    regime = "TRENDING" if persistence > 0.55 else "CHOPPY"

    # Stat score contribution: 0-100
    stat_score = round(float(np.clip((exp5d + 3) / 6 * 100, 0, 100)), 1)

    return MarkovAnalysis(
        current_state=cur,
        prob_bull_tomorrow=round(p["BULL"], 3),
        prob_bear_tomorrow=round(p["BEAR"], 3),
        prob_sideways_tomorrow=round(p["SIDEWAYS"], 3),
        state_persistence=round(persistence, 3),
        expected_return_5d=exp5d,
        regime_signal=regime,
        stat_score=stat_score,
    )


def _compute_kalman(closes: pd.Series) -> KalmanState:
    prices = closes.values.astype(float)
    x = np.array([prices[0], 0.0])
    P = np.eye(2)
    F = np.array([[1,1],[0,1]])
    H = np.array([[1,0]])
    Q = np.eye(2) * 1e-5
    R = 1e-3
    filtered = np.zeros(len(prices))
    gains    = np.zeros(len(prices))
    for i, obs in enumerate(prices):
        x = F @ x;  P = F @ P @ F.T + Q
        S = float((H @ P @ H.T)[0,0]) + R
        K = ((P @ H.T) / S).flatten()          # always shape (2,) — avoids ndim>0 scalar warnings
        x = x + K * (obs - float((H @ x)[0]))
        P = (np.eye(2) - np.outer(K, H)) @ P
        filtered[i] = x[0]; gains[i] = K[0]   # both plain scalars now

    fv = filtered[-1]
    noise_std = np.std(prices - filtered) + 1e-9
    kz = round((prices[-1] - fv) / noise_std, 2)
    sig = "ABOVE_FAIR" if kz > 1 else "BELOW_FAIR" if kz < -1 else "FAIR"
    return KalmanState(round(fv,2), round(float(x[1]),4), kz, sig, round(float(gains[-1]),5))


def _compute_hurst(closes: pd.Series) -> HurstResult:
    # Structure-function (generalised Hurst) estimator on LOG PRICE.
    #
    # The previous version ran R/S analysis on the log-PRICE level, which is
    # biased to H≈1 for essentially every name: price is the cumulative sum of
    # returns, so its rescaled range grows almost linearly with the lag no
    # matter the underlying dynamics. That made the regime flag useless — it
    # tagged every ticker "TRENDING" (observed: 0.92–1.00 across the board),
    # which is exactly why the momentum signal lacked persistence validation.
    #
    # The structure function regresses log(std of lag-step log-price changes)
    # on log(lag); the slope IS the Hurst exponent and is correctly centred at
    # 0.5 for a random walk, <0.45 for mean-reverting, >0.55 for persistent.
    prices = np.log(closes.tail(252).values.astype(float))
    n_total = len(prices)
    conf = "HIGH" if n_total >= 200 else ("MEDIUM" if n_total >= 100 else "LOW")
    lags = [l for l in range(2, 40) if l < n_total // 2]
    if len(lags) < 5:
        return HurstResult(0.5, "RANDOM", "insufficient data", "LOW")
    tau = np.array([np.std(prices[lag:] - prices[:-lag]) for lag in lags])
    mask = tau > 0
    if mask.sum() < 5:
        return HurstResult(0.5, "RANDOM", "insufficient data", "LOW")
    H = float(np.clip(np.polyfit(np.log(np.array(lags)[mask]),
                                 np.log(tau[mask]), 1)[0], 0, 1))
    H = round(H, 3)
    if   H < 0.45: interp, fit = "MEAN_REVERTING", "stat-arb / Z-score / pairs trading"
    elif H > 0.55: interp, fit = "TRENDING",        "momentum / trend following / breakout"
    else:           interp, fit = "RANDOM",          "no strong edge — use other signals"
    return HurstResult(H, interp, fit, conf)


def _compute_mean_reversion(closes: pd.Series) -> MeanReversionSignal:
    price = float(closes.iloc[-1])
    ma20  = float(closes.rolling(20).mean().iloc[-1])
    std20 = float(closes.rolling(20).std().iloc[-1]) or 1e-9
    ma50  = float(closes.rolling(50).mean().iloc[-1])
    std50 = float(closes.rolling(50).std().iloc[-1]) or 1e-9
    z20   = (price-ma20)/std20
    z50   = (price-ma50)/std50
    boll  = (price-(ma20-2*std20)) / (4*std20+1e-9)
    return MeanReversionSignal(
        zscore_20d=round(z20,2), zscore_50d=round(z50,2),
        bollinger_pct=round(boll,3),
        is_oversold=z20 < -1.5, is_overbought=z20 > 1.5,
        signal_strength=round(float(np.clip(-z20/2,-1,1)),3),
    )


def _compute_statistical(closes: pd.Series) -> StatisticalScore:
    markov = _compute_markov(closes)
    kalman = _compute_kalman(closes)
    hurst  = _compute_hurst(closes)
    mr     = _compute_mean_reversion(closes)

    # Statistical composite 0-100
    markov_c = markov.stat_score * 0.30
    kalman_c = float(np.clip((-kalman.kalman_zscore + 2) / 4 * 100, 0, 100)) * 0.30
    hurst_c  = (100 if hurst.interpretation=="MEAN_REVERTING" else
                50  if hurst.interpretation=="RANDOM" else 35) * 0.15  # mean-rev favored for oversold
    mr_c     = float((mr.signal_strength + 1) / 2 * 100) * 0.25

    # Regime gate (fixes "the model shorts the winners"): the statistical score
    # is a mean-reversion / oversold scanner, so a strong UPTREND reads as
    # "overbought" and drags the score toward SELL — exactly wrong for momentum
    # names like BEAM / RXRX. When Hurst says the regime is TRENDING, momentum
    # persists, so don't let the overbought mean-reversion term punish it: floor
    # the MR contribution at neutral.
    if hurst.interpretation == "TRENDING":
        mr_c = max(mr_c, 50 * 0.25)

    composite = round(markov_c + kalman_c + hurst_c + mr_c, 1)

    if   composite >= 72: sig = "STRONG_BUY"
    elif composite >= 58: sig = "BUY"
    elif composite >= 42: sig = "HOLD"
    elif composite >= 28: sig = "SELL"
    else:                 sig = "STRONG_SELL"

    return StatisticalScore(markov=markov, kalman=kalman, hurst=hurst,
                            mean_reversion=mr, composite_score=composite, signal=sig)


def compute_entry_quality(macd: "MACDSignal", hurst: HurstResult,
                          mr: MeanReversionSignal) -> EntryQuality:
    """
    Combine momentum DIRECTION (MACD) + momentum PERSISTENCE (Hurst) +
    over-extension (Bollinger) into a single "buy today vs wait" call.

    Decision matrix (the actual product the user asked for):
      MACD↑ + Hurst trending + not over-band   → BUY_NOW       (real, fresh trend)
      MACD↑ + over upper band                  → WAIT_PULLBACK (right idea, wrong price)
      MACD↑ + Hurst mean-reverting             → AVOID         (fake momentum, will snap back)
      MACD↓ + Hurst mean-reverting + oversold  → WATCH_BOUNCE  (faded extreme, small probe)
      MACD↓ + Hurst trending                   → AVOID         (real downtrend, don't catch)
      otherwise                                → NEUTRAL       (no clean edge — wait)
    """
    bb = mr.bollinger_pct
    if   bb > 0.95: bb_flag = "OVERBOUGHT"
    elif bb < 0.05: bb_flag = "OVERSOLD"
    else:           bb_flag = "NORMAL"

    mom_up = bool(macd.histogram > 0 or macd.bullish_cross
                  or macd.trend_strength in ("BULL", "STRONG_BULL"))
    mom_dn = bool(macd.histogram < 0 and macd.trend_strength in ("BEAR", "STRONG_BEAR"))
    trending = hurst.interpretation == "TRENDING"
    meanrev  = hurst.interpretation == "MEAN_REVERTING"

    # ── Discrete recommendation, then a score anchored to it so the two never
    #    disagree (rating is the headline; score adds within-band granularity). ──
    if mom_up and bb_flag == "OVERBOUGHT":
        rating, base = "WAIT_PULLBACK", 50
        note = f"momentum up but through upper band (BB={bb:.2f}) — limit-order a pullback toward the mid band"
    elif mom_up and meanrev:
        rating, base = "AVOID", 28
        note = f"momentum is fake — Hurst={hurst.hurst:.2f} (mean-reverting), the move will snap back; don't chase"
    elif mom_up and trending:
        rating, base = "BUY_NOW", 78
        note = f"real, persistent uptrend (Hurst={hurst.hurst:.2f}) and not over-extended (BB={bb:.2f}) — buyable today"
    elif mom_up:
        rating, base = "NEUTRAL", 50
        note = f"momentum up but trend persistence unconfirmed (Hurst={hurst.hurst:.2f}) — wait for follow-through"
    elif mom_dn and meanrev and bb_flag == "OVERSOLD":
        rating, base = "WATCH_BOUNCE", 55
        note = f"faded oversold extreme (BB={bb:.2f}, Hurst={hurst.hurst:.2f}) — only a small mean-reversion probe"
    elif mom_dn:
        rating, base = "AVOID", 22
        note = f"real downtrend (Hurst={hurst.hurst:.2f}) — don't catch the falling knife"
    else:
        rating, base = "NEUTRAL", 48
        note = "no clean directional edge — wait for a clearer entry"

    # Within-band nudges (kept small so they can't flip the headline band).
    score = float(base)
    if rating == "BUY_NOW":
        if macd.bullish_cross or macd.zero_cross_up: score += 8   # fresh cross = better entry
        if bb < 0.6:                                 score += 6   # more room before the band
    elif rating == "WAIT_PULLBACK":
        score -= min(15, (bb - 0.95) * 100)                       # the more extended, the worse
    score = round(float(np.clip(score, 0, 100)), 1)

    return EntryQuality(rating=rating, score=score, bb_position=round(bb, 3),
                        bb_flag=bb_flag, note=note)


# ══════════════════════════════════════════════════════════════════════════════
# FUNDAMENTAL SUB-MODULE
# ══════════════════════════════════════════════════════════════════════════════

def _compute_fundamental(sd) -> FundamentalScore:
    def val_s(pe, pb, ps):
        s = 5.0
        if pe:  s += 3 if pe<15 else 1.5 if pe<25 else 0 if pe<40 else -1.5 if pe<60 else -3
        if pb:  s += 1 if pb<2 else 0.5 if pb<5 else -1 if pb>20 else 0
        if ps:  s += 1 if ps<5 else -0.5 if ps>20 else 0
        return round(float(np.clip(s,0,10)),2)

    def _noisy_microcap_growth(rev, mcap):
        """A +200%+ YoY revenue print off a sub-$1B base is usually noise from a
        tiny denominator (e.g. $0.1M → $10M = +9900%), not durable growth. Flag
        it so we give partial — not maximal — growth credit."""
        return rev is not None and rev > 200 and mcap is not None and mcap < 1.0

    def grw_s(rev, earn, mcap=None):
        s = 5.0
        if rev is not None:
            if _noisy_microcap_growth(rev, mcap):
                s += 1.0   # extreme growth off a micro base — discount it
            else:
                s += 3 if rev>50 else 2 if rev>25 else 1 if rev>10 else -2 if rev<0 else 0
        if earn: s += 2 if earn>50 else 1 if earn>20 else -1 if earn<0 else 0
        return round(float(np.clip(s,0,10)),2)

    def qmj_quality(sd):
        """
        AQR Quality Minus Junk — three pillars, each mapped to 0-10:
          Profitability (net margin + ROE), Growth (prior earnings/revenue growth),
          Safety (low leverage + positive earnings). Quality = their average.
        Returns (quality, profitability, growth, safety).
        """
        margin = getattr(sd, "profit_margin", None)
        rev    = getattr(sd, "revenue_growth", None)
        earn   = getattr(sd, "earnings_growth", None)
        roe    = getattr(sd, "return_on_equity", None)   # %
        dte    = getattr(sd, "debt_to_equity", None)     # leverage in ×
        upside = getattr(sd, "upside_to_target", None)

        # ── Profitability — high returns on capital ──
        prof = 5.0
        if margin is not None:
            prof += 3 if margin > 25 else 1.5 if margin > 12 else 0.5 if margin > 0 else -3
        if roe is not None:
            prof += 2 if roe > 25 else 1 if roe > 12 else 0 if roe >= 0 else -1.5
        prof = round(float(np.clip(prof, 0, 10)), 2)

        # ── Growth — is the quality rising? ──
        mcap = getattr(sd, "market_cap_b", None)
        grow = 5.0
        if earn is not None:
            grow += 2.5 if earn > 25 else 1.5 if earn > 10 else 0 if earn >= 0 else -2.5
        if rev is not None:
            if _noisy_microcap_growth(rev, mcap):
                grow += 0.5   # micro-cap extreme-growth noise — minimal credit
            else:
                grow += 2.5 if rev > 25 else 1.5 if rev > 10 else 0 if rev >= 0 else -2.0
        grow = round(float(np.clip(grow, 0, 10)), 2)

        # ── Safety — low leverage, profitable, analyst support ──
        safe = 5.0
        if dte is not None:
            safe += 3 if dte < 0.3 else 1.5 if dte < 0.7 else 0 if dte < 1.5 else -2 if dte < 3 else -3
        if earn is not None and earn > 0: safe += 1
        if margin is not None and margin > 10: safe += 0.5
        if upside is not None and upside > 20: safe += 0.5
        safe = round(float(np.clip(safe, 0, 10)), 2)

        quality = round((prof + grow + safe) / 3, 2)
        return quality, prof, grow, safe

    def mom_s(r1m, r6m, r1y):
        s = 5.0
        if r1y: s += 3 if r1y>50 else 1.5 if r1y>20 else -1.5 if r1y<-10 else 0
        if r6m: s += 1.5 if r6m>20 else -1 if r6m<-10 else 0
        if r1m: s += 0.5 if r1m>10 else -0.5 if r1m<-10 else 0
        return round(float(np.clip(s,0,10)),2)

    v = val_s(sd.pe_ratio, sd.pb_ratio, sd.ps_ratio)
    g = grw_s(sd.revenue_growth, sd.earnings_growth, getattr(sd, "market_cap_b", None))
    q, q_prof, q_grow, q_safe = qmj_quality(sd)
    m = mom_s(sd.return_1m, sd.return_6m, sd.return_1y)
    composite = round(0.25*v + 0.30*g + 0.25*q + 0.20*m, 2)

    peg = None
    if sd.pe_ratio and sd.earnings_growth and sd.earnings_growth > 0:
        peg = round(sd.pe_ratio / sd.earnings_growth, 2)

    if peg is not None:
        garp = "CHEAP" if peg<1 else "FAIR" if peg<2 else "EXPENSIVE" if peg<3 else "VERY_EXPENSIVE"
    elif getattr(sd, "forward_pe", None) and getattr(sd, "revenue_growth", None) and sd.revenue_growth > 0:
        garp = "CHEAP" if sd.forward_pe/sd.revenue_growth<0.5 else "FAIR" if sd.forward_pe/sd.revenue_growth<1.2 else "EXPENSIVE"
    else:
        garp = "N/A"

    return FundamentalScore(v, g, q, m, composite, peg, garp,
                            qmj_profitability=q_prof, qmj_growth=q_grow, qmj_safety=q_safe)


# ══════════════════════════════════════════════════════════════════════════════
# SPY CACHE
# ══════════════════════════════════════════════════════════════════════════════

_SPY_RETURN_1Y: Optional[float] = None

def _get_spy_1y() -> float:
    global _SPY_RETURN_1Y
    if _SPY_RETURN_1Y is not None: return _SPY_RETURN_1Y
    try:
        import yfinance as yf
        c = yf.Ticker("SPY").history(period="13mo")["Close"].dropna()
        _SPY_RETURN_1Y = round((float(c.iloc[-1])/float(c.iloc[-253])-1)*100, 2)
        return _SPY_RETURN_1Y
    except Exception:
        return 20.0


# ══════════════════════════════════════════════════════════════════════════════
# MASTER BUILD
# ══════════════════════════════════════════════════════════════════════════════

def build_quant_report(sd, closes: pd.Series, hist_df: pd.DataFrame = None) -> QuantReport:
    """
    Build complete quant report with 5 sub-scores.
    hist_df (with High/Low/Close/Volume) needed for technical indicators.
    If not provided, we create a minimal DataFrame from closes only.
    """
    if hist_df is None or "High" not in hist_df.columns:
        # Fallback: use close-only approximations
        hist_df = pd.DataFrame({
            "Close": closes, "High": closes, "Low": closes,
            "Volume": pd.Series(np.ones(len(closes))*1e6, index=closes.index)
        })

    is_etf  = getattr(sd, "is_etf", False)
    is_gem  = getattr(sd, "gem_category", None) is not None

    # ── Compute all sub-modules ──
    tech  = compute_technical_score(closes, hist_df)
    stat  = _compute_statistical(closes)
    ml    = compute_ml_trend(closes)
    vol   = compute_volatility_regime(closes)
    risk  = compute_risk_metrics(closes)
    fund  = _compute_fundamental(sd)

    # ── Weighted composite ──
    t = tech.composite_score
    s = stat.composite_score
    m = ml.ml_score
    r = risk.risk_score
    f = fund.composite_score * 10   # 0-10 → 0-100

    if is_etf:
        overall = t*0.30 + s*0.30 + m*0.20 + r*0.20
    elif is_gem:
        # Speculative: less weight on fundamentals, more on technical+statistical
        overall = t*0.30 + s*0.30 + m*0.20 + r*0.10 + f*0.10
    else:
        overall = t*0.20 + s*0.25 + m*0.15 + r*0.15 + f*0.25

    overall = round(overall, 1)

    # Momentum-quality guard (fixes "the model shorts the winners"): a strong,
    # high-quality uptrend should not be tagged SELL just because mean-reversion
    # reads it as overbought. If a real grower is in a confirmed uptrend, floor
    # the score at HOLD so momentum names like BEAM / RXRX aren't flagged SELL.
    strong_growth = (getattr(sd, "revenue_growth", 0) or 0) > 25
    strong_uptrend = (ml.trend_signal in ("STRONG_UP", "UP")
                      and stat.hurst.interpretation != "MEAN_REVERTING"
                      and (getattr(sd, "return_1y", 0) or 0) > 0)
    if strong_growth and strong_uptrend and not is_etf:
        overall = max(overall, 50.0)

    # ── Analyst sentiment factor (was missing — fixes "SELL but analyst +33%") ─
    # Fold the sell-side target upside into the score as a genuine, bounded
    # factor instead of ignoring it. Strong consensus upside lifts the score;
    # consensus downside trims it.
    upside = getattr(sd, "upside_to_target", None)
    if upside is not None and not is_etf:
        if   upside > 30: overall += 3.0
        elif upside > 15: overall += 1.5
        elif upside < -10: overall -= 2.0
        overall = round(float(np.clip(overall, 0, 100)), 1)

    if   overall >= 72: sig = "STRONG_BUY"
    elif overall >= 58: sig = "BUY"
    elif overall >= 42: sig = "HOLD"
    elif overall >= 28: sig = "SELL"
    else:               sig = "STRONG_SELL"

    # ── Conflict arbitration: surface when the factors disagree, and don't let
    # the model fight a strong analyst conviction blindly (lift SELL→HOLD). ────
    conflicts = []
    r1m = getattr(sd, "return_1m", 0) or 0
    r1y = getattr(sd, "return_1y", 0) or 0
    if sig not in ("STRONG_BUY", "BUY") and upside is not None and upside > 25:
        conflicts.append(f"analyst sees +{upside:.0f}% upside but model says {sig}")
        if overall < 42:                      # rescue out of the SELL band to HOLD
            overall, sig = 42.0, "HOLD"
    if (r1m > 5 and r1y < -15) or (r1m < -5 and r1y > 15):
        conflicts.append(f"timeframe split: 1M {r1m:+.0f}% vs 1Y {r1y:+.0f}%")
    if ml.trend_signal in ("STRONG_UP", "UP") and stat.composite_score < 40:
        conflicts.append("momentum up but mean-reversion bearish (extended)")
    if fund.composite_score >= 7 and sig in ("SELL", "STRONG_SELL"):
        conflicts.append(f"strong fundamentals (F={fund.composite_score:.1f}) vs technical {sig}")

    # ── Entry-timing overlay (separate from the long-term score) ──
    entry = compute_entry_quality(tech.macd, stat.hurst, stat.mean_reversion)

    # ── Thesis ──
    parts = []
    mr = stat.mean_reversion
    kl = stat.kalman
    hu = stat.hurst
    mc = stat.markov
    if mr.is_oversold:                       parts.append(f"oversold Z={mr.zscore_20d:+.1f}")
    if kl.signal == "BELOW_FAIR":            parts.append(f"below Kalman fair (Kz={kl.kalman_zscore:+.1f})")
    if tech.macd.bullish_cross:              parts.append("MACD bullish cross")
    if tech.stochastic.bullish_cross:        parts.append(f"Stochastic cross ({tech.stochastic.k_pct:.0f})")
    if tech.obv.price_obv_divergence == "BULLISH_DIV": parts.append("OBV bullish divergence")
    if hu.interpretation == "MEAN_REVERTING":parts.append(f"Hurst={hu.hurst:.2f}(mean-rev)")
    if mc.prob_bull_tomorrow > 0.55:         parts.append(f"Markov P(bull)={mc.prob_bull_tomorrow:.0%}")
    if fund.garp_rating in ("CHEAP","FAIR"): parts.append(f"GARP={fund.garp_rating}")
    if fund.quality_score >= 7.5:            parts.append(f"high quality (QMJ={fund.quality_score:.1f})")
    if ml.trend_signal in ("STRONG_UP","UP"):parts.append(f"ML trend up (R²={ml.r_squared_20d:.2f})")
    if upside is not None and upside > 15:   parts.append(f"analyst +{upside:.0f}% upside")
    if not parts:                            parts.append("no strong directional signal")

    conflict_str = (" ⚠️ conflicts: " + "; ".join(conflicts)) if conflicts else ""
    entry_str = f" ⏱ entry: {entry.rating} — {entry.note}"

    return QuantReport(
        ticker=sd.ticker, technical=tech, statistical=stat,
        ml_trend=ml, vol_regime=vol, risk=risk, fundamental=fund,
        overall_quant_score=overall, signal_type=sig,
        quant_thesis=f"[{sig}] " + " | ".join(parts) + conflict_str + entry_str,
        signal_conflicts="; ".join(conflicts),
        entry_quality=entry,
    )


_ENTRY_BADGE = {
    "BUY_NOW":       "🟢 BUY NOW",
    "WAIT_PULLBACK": "🟡 WAIT DIP",
    "WATCH_BOUNCE":  "🔵 PROBE",
    "AVOID":         "🔴 AVOID",
    "NEUTRAL":       "⚪ WAIT",
}


def entry_badge(qr: QuantReport) -> str:
    """Short coloured Entry-Quality badge for screener / sector tables."""
    if not qr.entry_quality:
        return "—"
    return _ENTRY_BADGE.get(qr.entry_quality.rating, qr.entry_quality.rating)


def format_quant_one_liner(qr: QuantReport) -> str:
    """Compact one-liner for table display."""
    t  = qr.technical
    s  = qr.statistical
    ml = qr.ml_trend
    r  = qr.risk
    return (
        f"T:{qr.technical.composite_score:.0f}|"
        f"S:{s.composite_score:.0f}|"
        f"ML:{ml.ml_score:.0f}|"
        f"R:{r.risk_score:.0f}|"
        f"RSI:{t.stochastic.k_pct:.0f}|"
        f"H:{s.hurst.hurst:.2f}|"
        f"BB:{s.mean_reversion.bollinger_pct:.2f}|"
        f"Kz:{s.kalman.kalman_zscore:+.1f}|"
        f"Entry:{qr.entry_quality.rating if qr.entry_quality else 'N/A'}|"
        f"GARP:{qr.fundamental.garp_rating}"
    )
