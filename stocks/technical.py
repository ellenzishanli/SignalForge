"""
Technical Analysis Engine
Indicators used by technical traders, quant desks, and algo funds.

Implemented:
  MACD      — Moving Average Convergence Divergence (trend momentum)
  Stochastic — %K/%D oscillator (overbought/oversold)
  ATR        — Average True Range (volatility)
  OBV        — On-Balance Volume (volume trend confirmation)
  VWAP       — Volume Weighted Average Price (institutional benchmark)
  Fibonacci  — Key retracement levels (support/resistance)
  ADX        — Average Directional Index (trend strength)
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class MACDSignal:
    """
    MACD = EMA(12) - EMA(26). Signal line = EMA(9) of MACD.
    Histogram = MACD - Signal.

    Interpretation:
      Bullish: MACD crosses above signal line (momentum turning up)
      Bearish: MACD crosses below signal line
      Histogram expanding positive → strengthening uptrend
      Histogram expanding negative → strengthening downtrend
      Zero-line crossover: strongest signal (trend change confirmed)

    Used by: trend-following funds, CTAs, momentum strategies.
    """
    macd_line: float          # EMA12 - EMA26
    signal_line: float        # EMA9 of MACD
    histogram: float          # MACD - signal (positive = bullish momentum)
    bullish_cross: bool       # MACD just crossed above signal
    bearish_cross: bool       # MACD just crossed below signal
    zero_cross_up: bool       # MACD crossed zero line upward (strong)
    trend_strength: str       # "STRONG_BULL" | "BULL" | "NEUTRAL" | "BEAR" | "STRONG_BEAR"
    score: float              # 0-100 (100 = most bullish)


@dataclass
class StochasticSignal:
    """
    %K = (close - lowest_low_14) / (highest_high_14 - lowest_low_14) * 100
    %D = 3-period SMA of %K (signal line)

    Interpretation:
      %K < 20: oversold → watch for bullish cross with %D
      %K > 80: overbought → watch for bearish cross with %D
      Bull: %K crosses above %D in oversold zone (<20)
      Bear: %K crosses below %D in overbought zone (>80)

    More sensitive than RSI — picks up reversals earlier.
    """
    k_pct: float              # fast stochastic (0-100)
    d_pct: float              # slow stochastic (0-100, signal line)
    is_oversold: bool         # K < 20
    is_overbought: bool       # K > 80
    bullish_cross: bool       # K crossed above D in oversold zone
    bearish_cross: bool       # K crossed below D in overbought zone
    score: float              # 0-100


@dataclass
class ATRVolatility:
    """
    ATR = Average True Range over 14 days.
    True Range = max(High-Low, |High-PrevClose|, |Low-PrevClose|)

    Interpretation:
      High ATR vs historical: elevated volatility (risk OR opportunity)
      ATR expanding: increasing uncertainty (can signal breakout)
      ATR contracting: coiling → potential energy for move

    ATR % = ATR / price → normalized volatility for comparison across stocks.
    Used for: stop-loss placement, position sizing, breakout detection.
    """
    atr_14: float             # 14-day ATR in $ terms
    atr_pct: float            # ATR as % of price
    atr_vs_avg: float         # current ATR / 60-day avg ATR (>1.2 = elevated)
    is_contracting: bool      # ATR trending down (potential breakout setup)
    is_expanding: bool        # ATR trending up (volatile period)
    volatility_regime: str    # "LOW" | "NORMAL" | "HIGH" | "EXTREME"


@dataclass
class OBVSignal:
    """
    OBV (On-Balance Volume): running total where volume is +/- based on price direction.
      Up day → +volume; Down day → -volume.

    Why it matters: price can be manipulated, but VOLUME is harder to fake.
      OBV rising while price flat → accumulation (smart money buying quietly)
      OBV falling while price flat → distribution (institutional selling)
      OBV diverges from price → early warning of trend change

    Used by: institutional flow analysts, market microstructure quants.
    """
    obv_current: float        # current OBV level
    obv_trend_20d: float      # slope of OBV over 20 days (positive = accumulation)
    obv_vs_ma20: float        # OBV / 20-day avg OBV - 1 (% above/below average)
    price_obv_divergence: str # "BULLISH_DIV" | "BEARISH_DIV" | "CONFIRMED" | "NEUTRAL"
    score: float              # 0-100


@dataclass
class FibonacciLevels:
    """
    Fibonacci Retracement: after a move, key reversal/support levels at:
      23.6%, 38.2%, 50.0%, 61.8%, 78.6% of the move

    Theory: based on the Fibonacci sequence; turns out these levels have
    self-fulfilling prophecy properties because so many traders watch them.

    Interpretation:
      Price near 38.2% or 61.8% retracement = high-probability support/resistance
      "Golden ratio" = 61.8% — strongest Fibonacci level
    """
    swing_high: float
    swing_low: float
    fib_236: float
    fib_382: float
    fib_500: float
    fib_618: float
    fib_786: float
    nearest_level: str        # e.g. "near 61.8% support"
    current_zone: str         # "BELOW_ALL" | "AT_236" | "AT_382" | "AT_500" | "AT_618" | "AT_786" | "ABOVE_ALL"


@dataclass
class ADXSignal:
    """
    ADX (Average Directional Index): measures TREND STRENGTH (not direction).
      ADX < 20: weak/absent trend → mean reversion strategies work better
      ADX 20-40: developing trend
      ADX > 40: strong trend → momentum strategies work better
      ADX > 60: very strong trend (rare)

    +DI and -DI show direction:
      +DI > -DI: uptrend
      -DI > +DI: downtrend
    """
    adx: float                # 0-100, trend strength
    plus_di: float            # positive directional indicator
    minus_di: float           # negative directional indicator
    trend_direction: str      # "UP" | "DOWN" | "SIDEWAYS"
    trend_strength: str       # "NONE" | "WEAK" | "MODERATE" | "STRONG" | "VERY_STRONG"
    score: float              # 0-100


@dataclass
class TechnicalScore:
    """Aggregate of all technical indicators → one composite Technical Score."""
    macd: MACDSignal
    stochastic: StochasticSignal
    atr: ATRVolatility
    obv: OBVSignal
    fibonacci: FibonacciLevels
    adx: ADXSignal
    composite_score: float    # 0-100 weighted composite
    signal: str               # "STRONG_BUY" | "BUY" | "HOLD" | "SELL" | "STRONG_SELL"
    technical_thesis: str     # one-line summary of technical setup


# ── MACD ──────────────────────────────────────────────────────────────────────

def compute_macd(closes: pd.Series, fast=12, slow=26, signal=9) -> MACDSignal:
    ema_fast = closes.ewm(span=fast, adjust=False).mean()
    ema_slow = closes.ewm(span=slow, adjust=False).mean()
    macd     = ema_fast - ema_slow
    sig_line = macd.ewm(span=signal, adjust=False).mean()
    hist     = macd - sig_line

    ml = float(macd.iloc[-1])
    sl = float(sig_line.iloc[-1])
    hl = float(hist.iloc[-1])
    hl_prev = float(hist.iloc[-2])
    ml_prev = float(macd.iloc[-2])
    sl_prev = float(sig_line.iloc[-2])

    bull_cross = ml > sl and ml_prev <= sl_prev
    bear_cross = ml < sl and ml_prev >= sl_prev
    zero_up    = ml > 0 and ml_prev <= 0

    if   ml > sl and hl > 0 and hl > hl_prev: strength = "STRONG_BULL"
    elif ml > sl and hl > 0:                   strength = "BULL"
    elif ml < sl and hl < 0 and hl < hl_prev:  strength = "STRONG_BEAR"
    elif ml < sl and hl < 0:                    strength = "BEAR"
    else:                                       strength = "NEUTRAL"

    # Score: 0-100
    # Histogram normalized to price context
    hist_norm = float(np.clip(hl / (abs(ml) + 1e-9), -3, 3))
    score = round(float((hist_norm / 3 + 1) / 2 * 100), 1)
    if bull_cross: score = min(100, score + 15)
    if bear_cross: score = max(0, score - 15)
    if zero_up:    score = min(100, score + 10)

    return MACDSignal(
        macd_line=round(ml, 4), signal_line=round(sl, 4), histogram=round(hl, 4),
        bullish_cross=bull_cross, bearish_cross=bear_cross, zero_cross_up=zero_up,
        trend_strength=strength, score=round(score, 1),
    )


# ── Stochastic ────────────────────────────────────────────────────────────────

def compute_stochastic(hist_df: pd.DataFrame, k_period=14, d_period=3) -> StochasticSignal:
    """hist_df needs High, Low, Close columns."""
    try:
        low14  = hist_df["Low"].rolling(k_period).min()
        high14 = hist_df["High"].rolling(k_period).max()
        k = ((hist_df["Close"] - low14) / (high14 - low14 + 1e-9)) * 100
        d = k.rolling(d_period).mean()

        kv = float(k.iloc[-1])
        dv = float(d.iloc[-1])
        kp = float(k.iloc[-2])
        dp = float(d.iloc[-2])

        oversold    = kv < 20
        overbought  = kv > 80
        bull_cross  = kv > dv and kp <= dp and kv < 30
        bear_cross  = kv < dv and kp >= dp and kv > 70

        # Score: 0-100 (oversold territory = higher score = more bullish)
        if oversold:
            score = 70 + (20 - kv) * 1.5
        elif overbought:
            score = 30 - (kv - 80) * 0.5
        else:
            score = 50 + (50 - kv) * 0.4

        if bull_cross: score += 15
        if bear_cross: score -= 15
        score = round(float(np.clip(score, 0, 100)), 1)

        return StochasticSignal(
            k_pct=round(kv, 1), d_pct=round(dv, 1),
            is_oversold=oversold, is_overbought=overbought,
            bullish_cross=bull_cross, bearish_cross=bear_cross, score=score,
        )
    except Exception:
        return StochasticSignal(50, 50, False, False, False, False, 50.0)


# ── ATR ───────────────────────────────────────────────────────────────────────

def compute_atr(hist_df: pd.DataFrame, period=14) -> ATRVolatility:
    try:
        high  = hist_df["High"]
        low   = hist_df["Low"]
        close = hist_df["Close"]
        prev_close = close.shift(1)

        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low  - prev_close).abs(),
        ], axis=1).max(axis=1)

        atr     = tr.rolling(period).mean()
        atr_60  = tr.rolling(60).mean()
        atr_val = float(atr.iloc[-1])
        price   = float(close.iloc[-1])
        avg60   = float(atr_60.iloc[-1]) if not np.isnan(float(atr_60.iloc[-1])) else atr_val
        ratio   = atr_val / avg60 if avg60 > 0 else 1.0

        atr_short = float(atr.tail(5).mean())
        atr_long  = float(atr.tail(20).mean())

        contracting = atr_short < atr_long * 0.85
        expanding   = atr_short > atr_long * 1.15

        if   ratio > 2.0: regime = "EXTREME"
        elif ratio > 1.5: regime = "HIGH"
        elif ratio > 1.2: regime = "ELEVATED"
        elif ratio < 0.7: regime = "LOW"
        else:             regime = "NORMAL"

        return ATRVolatility(
            atr_14=round(atr_val, 3),
            atr_pct=round(atr_val / price * 100, 2),
            atr_vs_avg=round(ratio, 2),
            is_contracting=contracting,
            is_expanding=expanding,
            volatility_regime=regime,
        )
    except Exception:
        return ATRVolatility(0, 0, 1.0, False, False, "NORMAL")


# ── OBV ───────────────────────────────────────────────────────────────────────

def compute_obv(hist_df: pd.DataFrame) -> OBVSignal:
    try:
        close  = hist_df["Close"]
        volume = hist_df["Volume"]
        direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
        obv = (direction * volume).cumsum()

        obv_curr  = float(obv.iloc[-1])
        obv_ma20  = float(obv.rolling(20).mean().iloc[-1])

        # OBV trend: linear regression slope over last 20 days
        y = obv.tail(20).values.astype(float)
        x = np.arange(len(y))
        slope = float(np.polyfit(x, y, 1)[0])

        # Price trend over same period
        py = close.tail(20).values.astype(float)
        price_slope = float(np.polyfit(x, py, 1)[0])

        obv_vs_ma = round((obv_curr - obv_ma20) / (abs(obv_ma20) + 1) * 100, 2)

        # Divergence detection
        if slope > 0 and price_slope < 0:
            div = "BULLISH_DIV"   # OBV up, price down → accumulation
        elif slope < 0 and price_slope > 0:
            div = "BEARISH_DIV"   # OBV down, price up → distribution
        elif slope > 0 and price_slope > 0:
            div = "CONFIRMED"     # both up → healthy trend
        else:
            div = "NEUTRAL"

        # Score
        base_score = 50 + float(np.clip(slope / (abs(slope) + 1e-9) * 20, -20, 20))
        if div == "BULLISH_DIV":  base_score += 20
        if div == "BEARISH_DIV":  base_score -= 20
        if div == "CONFIRMED":    base_score += 10
        score = round(float(np.clip(base_score, 0, 100)), 1)

        return OBVSignal(
            obv_current=obv_curr, obv_trend_20d=round(slope, 2),
            obv_vs_ma20=obv_vs_ma, price_obv_divergence=div, score=score,
        )
    except Exception:
        return OBVSignal(0, 0, 0, "NEUTRAL", 50.0)


# ── Fibonacci ─────────────────────────────────────────────────────────────────

def compute_fibonacci(closes: pd.Series, window: int = 60) -> FibonacciLevels:
    """Compute Fibonacci retracement from the recent swing high/low."""
    tail  = closes.tail(window)
    high  = float(tail.max())
    low   = float(tail.min())
    price = float(closes.iloc[-1])
    move  = high - low

    fibs = {
        "fib_236": high - 0.236 * move,
        "fib_382": high - 0.382 * move,
        "fib_500": high - 0.500 * move,
        "fib_618": high - 0.618 * move,
        "fib_786": high - 0.786 * move,
    }

    # Find nearest level
    nearest_key = min(fibs, key=lambda k: abs(fibs[k] - price))
    nearest_dist = abs(fibs[nearest_key] - price) / price * 100

    if nearest_dist < 3:
        zone = nearest_key.replace("fib_", "AT_")
        nearest = f"near {nearest_key.replace('fib_', '')}% level (${fibs[nearest_key]:.2f})"
    elif price > high:
        zone, nearest = "ABOVE_ALL", "above all Fibonacci levels (strong)"
    elif price < fibs["fib_786"]:
        zone, nearest = "BELOW_ALL", "below all Fibonacci levels (weak)"
    else:
        zone, nearest = "BETWEEN_LEVELS", f"between Fibonacci levels"

    return FibonacciLevels(
        swing_high=round(high, 2), swing_low=round(low, 2),
        fib_236=round(fibs["fib_236"], 2), fib_382=round(fibs["fib_382"], 2),
        fib_500=round(fibs["fib_500"], 2), fib_618=round(fibs["fib_618"], 2),
        fib_786=round(fibs["fib_786"], 2),
        nearest_level=nearest, current_zone=zone,
    )


# ── ADX ───────────────────────────────────────────────────────────────────────

def compute_adx(hist_df: pd.DataFrame, period: int = 14) -> ADXSignal:
    try:
        high  = hist_df["High"]
        low   = hist_df["Low"]
        close = hist_df["Close"]

        up_move   = high.diff()
        down_move = -low.diff()
        plus_dm   = up_move.where((up_move > down_move) & (up_move > 0), 0)
        minus_dm  = down_move.where((down_move > up_move) & (down_move > 0), 0)

        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low  - close.shift(1)).abs(),
        ], axis=1).max(axis=1)

        atr14     = tr.rolling(period).mean()
        plus_di   = 100 * plus_dm.rolling(period).mean() / (atr14 + 1e-9)
        minus_di  = 100 * minus_dm.rolling(period).mean() / (atr14 + 1e-9)
        dx        = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9)
        adx_val   = dx.rolling(period).mean()

        adx_v  = round(float(adx_val.iloc[-1]), 1)
        pdi_v  = round(float(plus_di.iloc[-1]), 1)
        mdi_v  = round(float(minus_di.iloc[-1]), 1)

        direction = "UP" if pdi_v > mdi_v else "DOWN"

        if   adx_v > 60: strength = "VERY_STRONG"
        elif adx_v > 40: strength = "STRONG"
        elif adx_v > 25: strength = "MODERATE"
        elif adx_v > 15: strength = "WEAK"
        else:             strength = "NONE"

        # Score: strong uptrend = high score
        base = adx_v  # 0-100
        if direction == "DOWN": base = 100 - base
        score = round(float(np.clip(base, 0, 100)), 1)

        return ADXSignal(
            adx=adx_v, plus_di=pdi_v, minus_di=mdi_v,
            trend_direction=direction, trend_strength=strength, score=score,
        )
    except Exception:
        return ADXSignal(20, 25, 25, "SIDEWAYS", "WEAK", 50.0)


# ── Composite Technical Score ─────────────────────────────────────────────────

def compute_technical_score(closes: pd.Series, hist_df: pd.DataFrame) -> TechnicalScore:
    """
    Combine all technical indicators into one composite score.
    Weights reflect importance in practice:
      MACD 25% | RSI/Stochastic 20% | OBV 20% | ADX 20% | ATR 15%
    """
    macd  = compute_macd(closes)
    stoch = compute_stochastic(hist_df)
    atr   = compute_atr(hist_df)
    obv   = compute_obv(hist_df)
    fib   = compute_fibonacci(closes)
    adx   = compute_adx(hist_df)

    composite = round(
        macd.score  * 0.25 +
        stoch.score * 0.20 +
        obv.score   * 0.20 +
        adx.score   * 0.20 +
        (100 - min(atr.atr_vs_avg * 40, 100)) * 0.15,  # low vol regime = better for longs
        1
    )

    if   composite >= 72: signal = "STRONG_BUY"
    elif composite >= 58: signal = "BUY"
    elif composite >= 42: signal = "HOLD"
    elif composite >= 28: signal = "SELL"
    else:                 signal = "STRONG_SELL"

    parts = []
    if macd.bullish_cross:       parts.append("MACD bullish cross")
    if macd.zero_cross_up:       parts.append("MACD zero-line cross")
    if stoch.bullish_cross:      parts.append("Stochastic oversold cross")
    if stoch.is_oversold:        parts.append(f"Stochastic oversold ({stoch.k_pct:.0f})")
    if obv.price_obv_divergence == "BULLISH_DIV": parts.append("OBV bullish divergence")
    if adx.trend_strength in ("STRONG", "VERY_STRONG") and adx.trend_direction == "UP":
        parts.append(f"ADX {adx.adx:.0f} strong uptrend")
    if atr.is_contracting:       parts.append("ATR contracting (coiling)")
    if not parts:                parts.append("no strong technical catalyst")

    return TechnicalScore(
        macd=macd, stochastic=stoch, atr=atr, obv=obv, fibonacci=fib, adx=adx,
        composite_score=composite, signal=signal,
        technical_thesis=f"[TECH:{signal}] " + " | ".join(parts),
    )
