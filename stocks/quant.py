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
class FundamentalScore:
    """
    Multi-factor fundamental model (Value/Growth/Quality/Momentum).
    Weights: Value 25% | Growth 30% | Quality 25% | Momentum 20%.
    PEG = PE / earnings_growth_rate (<1 = cheap for growth, GARP ideal).
    """
    value_score: float
    growth_score: float
    quality_score: float
    momentum_score: float
    composite_score: float          # 0-10
    peg_ratio: Optional[float]
    garp_rating: str


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
    prices = np.log(closes.tail(200).values.astype(float))
    n_total = len(prices)
    conf = "HIGH" if n_total >= 200 else ("MEDIUM" if n_total >= 100 else "LOW")
    lags = [l for l in [10,20,40,80,100] if l < n_total//2]
    if len(lags) < 3:
        return HurstResult(0.5, "RANDOM", "insufficient data", "LOW")
    rs_vals = []
    for lag in lags:
        rs_sub = []
        for s in range(0, n_total-lag, lag):
            sub = prices[s:s+lag]
            dev = np.cumsum(sub - sub.mean())
            rs_sub.append((dev.max()-dev.min()) / (sub.std()+1e-9))
        rs_vals.append(np.mean(rs_sub))
    H = float(np.clip(np.polyfit(np.log(lags), np.log(np.array(rs_vals)+1e-9), 1)[0], 0, 1))
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

    composite = round(markov_c + kalman_c + hurst_c + mr_c, 1)

    if   composite >= 72: sig = "STRONG_BUY"
    elif composite >= 58: sig = "BUY"
    elif composite >= 42: sig = "HOLD"
    elif composite >= 28: sig = "SELL"
    else:                 sig = "STRONG_SELL"

    return StatisticalScore(markov=markov, kalman=kalman, hurst=hurst,
                            mean_reversion=mr, composite_score=composite, signal=sig)


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

    def grw_s(rev, earn):
        s = 5.0
        if rev:  s += 3 if rev>50 else 2 if rev>25 else 1 if rev>10 else -2 if rev<0 else 0
        if earn: s += 2 if earn>50 else 1 if earn>20 else -1 if earn<0 else 0
        return round(float(np.clip(s,0,10)),2)

    def qlt_s(margin, upside):
        s = 5.0
        if margin: s += 3 if margin>30 else 1.5 if margin>15 else 0.5 if margin>0 else -2
        if upside and upside > 20: s += 1
        return round(float(np.clip(s,0,10)),2)

    def mom_s(r1m, r6m, r1y):
        s = 5.0
        if r1y: s += 3 if r1y>50 else 1.5 if r1y>20 else -1.5 if r1y<-10 else 0
        if r6m: s += 1.5 if r6m>20 else -1 if r6m<-10 else 0
        if r1m: s += 0.5 if r1m>10 else -0.5 if r1m<-10 else 0
        return round(float(np.clip(s,0,10)),2)

    v = val_s(sd.pe_ratio, sd.pb_ratio, sd.ps_ratio)
    g = grw_s(sd.revenue_growth, sd.earnings_growth)
    q = qlt_s(sd.profit_margin, sd.upside_to_target)
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

    return FundamentalScore(v, g, q, m, composite, peg, garp)


# ══════════════════════════════════════════════════════════════════════════════
# SPY CACHE
# ══════════════════════════════════════════════════════════════════════════════

_SPY_RETURN_1Y: Optional[float] = None

def _get_spy_1y() -> float:
    global _SPY_RETURN_1Y
    if _SPY_RETURN_1Y is not None: return _SPY_RETURN_1Y
    try:
        import yfinance as yf
        c = yf.Ticker("SPY").history(period="13mo")["Close"]
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

    if   overall >= 72: sig = "STRONG_BUY"
    elif overall >= 58: sig = "BUY"
    elif overall >= 42: sig = "HOLD"
    elif overall >= 28: sig = "SELL"
    else:               sig = "STRONG_SELL"

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
    if ml.trend_signal in ("STRONG_UP","UP"):parts.append(f"ML trend up (R²={ml.r_squared_20d:.2f})")
    if not parts:                            parts.append("no strong directional signal")

    return QuantReport(
        ticker=sd.ticker, technical=tech, statistical=stat,
        ml_trend=ml, vol_regime=vol, risk=risk, fundamental=fund,
        overall_quant_score=overall, signal_type=sig,
        quant_thesis=f"[{sig}] " + " | ".join(parts),
    )


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
        f"Kz:{s.kalman.kalman_zscore:+.1f}|"
        f"GARP:{qr.fundamental.garp_rating}"
    )
