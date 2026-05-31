"""
Risk Metrics & ML Signals
Tools used by risk managers, portfolio constructors, and quant researchers.

Implemented:
  Sharpe Ratio     — risk-adjusted return (annualized)
  Sortino Ratio    — downside-adjusted return (only penalizes bad volatility)
  Max Drawdown     — largest peak-to-trough decline
  VaR (99%)        — worst expected 1-day loss at 99% confidence
  CVaR/ES          — Expected Shortfall (average loss beyond VaR)
  Beta             — sensitivity to SPY market moves
  Correlation      — vs SPY, vs VIX, vs GLD (safe haven correlation)
  Calmar Ratio     — return / max drawdown
  ML Trend Model   — linear regression + R² + prediction band
  Volatility Regime — GARCH-inspired volatility state detection
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional


@dataclass
class RiskMetrics:
    """
    Core risk statistics — what every risk desk monitors.

    Sharpe Ratio: (Return - RiskFreeRate) / Volatility
      > 2.0: excellent | 1.0-2.0: good | 0-1.0: acceptable | < 0: bad

    Sortino Ratio: like Sharpe but only penalizes DOWNSIDE volatility.
      Better for assets with positive skew (asymmetric returns).

    Max Drawdown: largest peak-to-trough decline.
      < -20%: normal for growth stocks | < -50%: extreme | -80%+: speculative

    VaR (99%): "We expect to lose no more than X% on 99% of trading days."
      Calculated as 1st percentile of historical daily returns.

    CVaR / Expected Shortfall: average loss on the worst 1% of days.
      More conservative than VaR; preferred by regulators (Basel IV).

    Beta: how much the stock moves per 1% SPY move.
      Beta=2 → stock moves 2% when SPY moves 1%.
      High beta = amplified market exposure (good in bull, bad in bear).

    Calmar: annualized_return / abs(max_drawdown).
      > 1.0: return compensates for drawdown risk.
    """
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float      # negative number, e.g. -35.2
    var_99_pct: float            # daily VaR at 99% confidence (negative)
    cvar_99_pct: float           # expected shortfall at 99% (negative, worse than VaR)
    annualized_vol: float        # annualized historical volatility %
    annualized_return: float     # trailing 1Y return annualized %
    beta_vs_spy: float           # market beta
    corr_vs_spy: float           # correlation with SPY
    corr_vs_vix: float           # correlation with VIX (positive = defensive)
    calmar_ratio: float
    risk_score: float            # 0-100 composite (100 = best risk profile)
    risk_label: str              # "LOW_RISK" | "MODERATE" | "HIGH_RISK" | "SPECULATIVE"


@dataclass
class MLTrendSignal:
    """
    ML-inspired trend signals using statistical regression.

    Linear Regression Trend:
      Fit y = a*t + b over last N days.
      Slope a > 0 → uptrend; R² → how reliable the trend is.
      Price vs regression band → is it extended or mean-reverting?

    Velocity + Acceleration:
      Velocity = 1st derivative of price (momentum)
      Acceleration = 2nd derivative (is momentum speeding up or slowing?)
      Positive velocity + positive acceleration = strong uptrend
      Positive velocity + negative acceleration = uptrend losing steam

    Trend Strength (R²):
      R² close to 1.0 → price moves in a very consistent linear trend
      R² close to 0.0 → price is random/choppy around a mean

    Breakout Probability:
      Based on ATR bands + momentum: how likely is a new high in next 5 days?
    """
    slope_20d: float            # linear regression slope (price per day)
    slope_pct_20d: float        # slope as % of current price per day
    r_squared_20d: float        # trend reliability 0-1
    price_vs_trend_band: float  # (price - regression line) / std → Z-score of trend deviation
    velocity: float             # price momentum (5d EMA of daily returns)
    acceleration: float         # change in velocity (positive = speeding up)
    trend_signal: str           # "STRONG_UP" | "UP" | "FLAT" | "DOWN" | "STRONG_DOWN"
    ml_score: float             # 0-100


@dataclass
class VolatilityRegime:
    """
    GARCH-inspired volatility regime detection.
    Even without fitting a full GARCH model, we can detect regimes:

    Realized volatility (short vs long window):
      Short vol < Long vol → volatility compressed (potential breakout)
      Short vol > Long vol → volatility expanding (turbulent period)

    Volatility of volatility (VoV):
      How much does daily vol itself vary? High VoV = unpredictable risk.

    Vol-adjusted return:
      Are we being compensated for the volatility we're taking?
    """
    vol_5d: float               # 5-day realized volatility (annualized %)
    vol_20d: float              # 20-day realized volatility
    vol_60d: float              # 60-day realized volatility
    vol_ratio_short_long: float # vol_5d / vol_60d (>1.2 = expanding)
    vol_of_vol: float           # std of rolling 5d vol
    regime: str                 # "QUIET" | "NORMAL" | "ELEVATED" | "CRISIS"
    vol_score: float            # 0-100 (100 = low, stable vol = good for longs)


# ── SPY Cache ─────────────────────────────────────────────────────────────────

_SPY_RETURNS_CACHE: Optional[pd.Series] = None
_VIX_RETURNS_CACHE: Optional[pd.Series] = None


def _get_spy_returns() -> pd.Series:
    global _SPY_RETURNS_CACHE
    if _SPY_RETURNS_CACHE is not None:
        return _SPY_RETURNS_CACHE
    try:
        import yfinance as yf
        spy = yf.Ticker("SPY").history(period="14mo")["Close"].pct_change().dropna()
        _SPY_RETURNS_CACHE = spy
        return spy
    except Exception:
        return pd.Series(dtype=float)


def _get_vix_returns() -> pd.Series:
    global _VIX_RETURNS_CACHE
    if _VIX_RETURNS_CACHE is not None:
        return _VIX_RETURNS_CACHE
    try:
        import yfinance as yf
        vix = yf.Ticker("^VIX").history(period="14mo")["Close"].pct_change().dropna()
        _VIX_RETURNS_CACHE = vix
        return vix
    except Exception:
        return pd.Series(dtype=float)


# ── Risk Metrics ──────────────────────────────────────────────────────────────

def compute_risk_metrics(closes: pd.Series, rf_daily: float = 0.00018) -> RiskMetrics:
    """
    rf_daily = daily risk-free rate (5% annual / 252 ≈ 0.018%).
    """
    rets = closes.pct_change().dropna()
    if len(rets) < 60:
        return RiskMetrics(0,0,-50,-3,-5,50,0,1,0.8,0,0,50,"MODERATE")

    ann_factor = np.sqrt(252)
    ann_ret    = float(((closes.iloc[-1] / closes.iloc[-253]) - 1) * 100) if len(closes) > 253 else float(((closes.iloc[-1] / closes.iloc[0]) - 1) * 100)
    vol_daily  = float(rets.std())
    ann_vol    = round(vol_daily * ann_factor * 100, 2)

    # Sharpe
    excess     = rets - rf_daily
    sharpe     = round(float(excess.mean() / (excess.std() + 1e-9) * ann_factor), 2)

    # Sortino (downside std only)
    downside_rets = rets[rets < rf_daily]
    down_std      = float(downside_rets.std()) if len(downside_rets) > 5 else vol_daily
    sortino       = round(float((rets.mean() - rf_daily) / (down_std + 1e-9) * ann_factor), 2)

    # Max Drawdown
    cumulative = (1 + rets).cumprod()
    rolling_max = cumulative.expanding().max()
    drawdown    = (cumulative - rolling_max) / rolling_max
    max_dd      = round(float(drawdown.min()) * 100, 2)

    # VaR & CVaR at 99%
    var_99  = round(float(np.percentile(rets, 1)) * 100, 2)
    cvar_99 = round(float(rets[rets <= np.percentile(rets, 1)].mean()) * 100, 2)

    # Beta & Correlation vs SPY
    spy_rets = _get_spy_returns()
    common   = rets.index.intersection(spy_rets.index)
    if len(common) > 60:
        r_aligned   = rets.loc[common]
        spy_aligned = spy_rets.loc[common]
        cov  = float(np.cov(r_aligned, spy_aligned)[0][1])
        var_ = float(spy_aligned.var())
        beta = round(cov / (var_ + 1e-9), 2)
        corr_spy = round(float(np.corrcoef(r_aligned, spy_aligned)[0][1]), 3)
    else:
        beta, corr_spy = 1.0, 0.8

    # Correlation vs VIX
    vix_rets  = _get_vix_returns()
    common_v  = rets.index.intersection(vix_rets.index)
    if len(common_v) > 60:
        corr_vix = round(float(np.corrcoef(rets.loc[common_v], vix_rets.loc[common_v])[0][1]), 3)
    else:
        corr_vix = -0.3

    # Calmar
    calmar = round(ann_ret / (abs(max_dd) + 1e-9), 2)

    # Risk Score (0-100, higher = better risk profile)
    score = 50.0
    score += max(-20, min(20, sharpe * 10))
    score += max(-20, min(20, (max_dd + 30) * 0.5))  # -30% dd = neutral
    score += max(-10, min(10, -beta * 3 + 3))         # low beta = better
    score += max(-10, min(10, (corr_vix + 0.5) * 10)) # positive VIX corr = defensive
    score = round(float(np.clip(score, 0, 100)), 1)

    if   score >= 70: label = "LOW_RISK"
    elif score >= 50: label = "MODERATE"
    elif score >= 30: label = "HIGH_RISK"
    else:             label = "SPECULATIVE"

    return RiskMetrics(
        sharpe_ratio=sharpe, sortino_ratio=sortino,
        max_drawdown_pct=max_dd, var_99_pct=var_99, cvar_99_pct=cvar_99,
        annualized_vol=ann_vol, annualized_return=round(ann_ret, 2),
        beta_vs_spy=beta, corr_vs_spy=corr_spy, corr_vs_vix=corr_vix,
        calmar_ratio=calmar, risk_score=score, risk_label=label,
    )


# ── ML Trend Signal ───────────────────────────────────────────────────────────

def compute_ml_trend(closes: pd.Series) -> MLTrendSignal:
    """Linear regression trend model."""
    price = float(closes.iloc[-1])
    tail  = closes.tail(20).values.astype(float)
    x     = np.arange(len(tail))

    # Fit linear regression
    coeffs = np.polyfit(x, tail, 1)
    slope  = float(coeffs[0])
    predicted = np.polyval(coeffs, x)
    residuals = tail - predicted
    ss_res = np.sum(residuals**2)
    ss_tot = np.sum((tail - tail.mean())**2)
    r2 = float(1 - ss_res / (ss_tot + 1e-9))

    # Price vs trend band (Z-score of deviation from regression)
    residual_std = float(np.std(residuals)) + 1e-9
    latest_pred  = float(np.polyval(coeffs, len(tail) - 1))
    price_vs_band = round((price - latest_pred) / residual_std, 2)

    # Velocity & acceleration (momentum dynamics)
    daily_rets  = pd.Series(closes.pct_change().dropna().tail(10))
    velocity    = round(float(daily_rets.ewm(span=5).mean().iloc[-1]) * 100, 4)
    accel       = round(float(daily_rets.diff().ewm(span=5).mean().iloc[-1]) * 100, 4)

    slope_pct = round(slope / price * 100, 4)

    if   slope_pct > 0.3 and r2 > 0.6:  trend = "STRONG_UP"
    elif slope_pct > 0.05:               trend = "UP"
    elif slope_pct < -0.3 and r2 > 0.6: trend = "STRONG_DOWN"
    elif slope_pct < -0.05:              trend = "DOWN"
    else:                                trend = "FLAT"

    # ML score
    score = 50.0
    score += float(np.clip(slope_pct * 100, -25, 25))
    score += r2 * 10                          # better R² = more reliable trend
    score += float(np.clip(-price_vs_band * 10, -15, 15))  # below trend = buy
    score += float(np.clip(velocity * 200, -10, 10))
    score = round(float(np.clip(score, 0, 100)), 1)

    return MLTrendSignal(
        slope_20d=round(slope, 4), slope_pct_20d=slope_pct,
        r_squared_20d=round(r2, 3), price_vs_trend_band=price_vs_band,
        velocity=velocity, acceleration=accel,
        trend_signal=trend, ml_score=score,
    )


def compute_volatility_regime(closes: pd.Series) -> VolatilityRegime:
    """Detect current volatility regime."""
    rets   = closes.pct_change().dropna()
    ann    = np.sqrt(252) * 100

    vol5   = round(float(rets.tail(5).std()) * ann, 2)
    vol20  = round(float(rets.tail(20).std()) * ann, 2)
    vol60  = round(float(rets.tail(60).std()) * ann, 2) if len(rets) >= 60 else vol20
    ratio  = round(vol5 / (vol60 + 1e-9), 2)

    # Vol of vol
    rolling_vol = rets.rolling(5).std() * ann
    vov = round(float(rolling_vol.dropna().tail(20).std()), 2)

    if   vol20 < 15:  regime = "QUIET"
    elif vol20 < 30:  regime = "NORMAL"
    elif vol20 < 50:  regime = "ELEVATED"
    else:             regime = "CRISIS"

    # Score: low/stable vol = good = higher score
    score = 100 - min(100, vol20 * 1.5)
    score = round(float(np.clip(score, 0, 100)), 1)

    return VolatilityRegime(
        vol_5d=vol5, vol_20d=vol20, vol_60d=vol60,
        vol_ratio_short_long=ratio, vol_of_vol=vov,
        regime=regime, vol_score=score,
    )
