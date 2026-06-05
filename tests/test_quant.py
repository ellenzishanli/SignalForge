"""
Unit tests for the quantitative analysis engine (stocks/quant.py).
"""
import sys
import os
import types
import pytest
import numpy as np
import pandas as pd
from types import SimpleNamespace

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from stocks.quant import (
    _compute_markov,
    _compute_kalman,
    _compute_hurst,
    _compute_mean_reversion,
    _compute_statistical,
    _compute_fundamental,
    build_quant_report,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_stock_data(ticker="TEST"):
    """Return a minimal SimpleNamespace mimicking screener StockData."""
    return SimpleNamespace(
        ticker=ticker,
        pe_ratio=20.0,
        pb_ratio=3.0,
        ps_ratio=5.0,
        forward_pe=18.0,
        revenue_growth=15.0,
        earnings_growth=20.0,
        profit_margin=18.0,
        return_1m=2.0,
        return_6m=10.0,
        return_1y=25.0,
        upside_to_target=12.0,
        is_etf=False,
        gem_category=None,
    )


# ── _compute_markov ───────────────────────────────────────────────────────────

class TestComputeMarkov:
    def test_score_in_range(self, trending_prices):
        result = _compute_markov(trending_prices)
        assert 0 <= result.stat_score <= 100

    def test_probabilities_sum_to_one(self, trending_prices):
        result = _compute_markov(trending_prices)
        total = result.prob_bull_tomorrow + result.prob_bear_tomorrow + result.prob_sideways_tomorrow
        assert abs(total - 1.0) < 1e-6

    def test_valid_state(self, trending_prices):
        result = _compute_markov(trending_prices)
        assert result.current_state in ("BULL", "BEAR", "SIDEWAYS")

    def test_regime_signal(self, trending_prices):
        result = _compute_markov(trending_prices)
        assert result.regime_signal in ("TRENDING", "CHOPPY")


# ── _compute_kalman ───────────────────────────────────────────────────────────

class TestComputeKalman:
    def test_signal_in_valid_set(self, trending_prices):
        result = _compute_kalman(trending_prices)
        assert result.signal in ("ABOVE_FAIR", "BELOW_FAIR", "FAIR")

    def test_filtered_price_is_float(self, trending_prices):
        result = _compute_kalman(trending_prices)
        assert isinstance(result.filtered_price, float)
        assert np.isfinite(result.filtered_price)

    def test_filtered_price_reasonable(self, trending_prices):
        result = _compute_kalman(trending_prices)
        # Should be in rough neighbourhood of actual prices
        assert 50 < result.filtered_price < 500


# ── _compute_hurst ────────────────────────────────────────────────────────────

class TestComputeHurst:
    def test_hurst_in_range(self, trending_prices):
        result = _compute_hurst(trending_prices)
        assert 0 <= result.hurst <= 1

    def test_interpretation_in_valid_set(self, trending_prices):
        result = _compute_hurst(trending_prices)
        assert result.interpretation in ("MEAN_REVERTING", "RANDOM", "TRENDING")

    def test_short_series_no_raise(self):
        """5-bar series should not raise; returns a LOW-confidence fallback."""
        short = pd.Series([100.0, 101.0, 99.5, 102.0, 100.5])
        result = _compute_hurst(short)
        assert result.confidence == "LOW"

    def test_flat_prices_valid(self, flat_prices):
        result = _compute_hurst(flat_prices)
        assert 0 <= result.hurst <= 1

    def test_random_walk_centred_near_half(self):
        """The structure-function estimator must NOT be biased to ~1 (the old
        R/S-on-price bug). A pure random walk should land near 0.5."""
        np.random.seed(42)
        rw = pd.Series(100 * np.exp(np.cumsum(np.random.normal(0, 0.01, 300))))
        h = _compute_hurst(rw).hurst
        assert 0.35 <= h <= 0.65, f"random walk H={h} — estimator is biased"


# ── compute_entry_quality ─────────────────────────────────────────────────────

from stocks.quant import compute_entry_quality


class TestEntryQuality:
    def _macd(self, hist, strength, bull=False):
        return SimpleNamespace(macd_line=0.0, signal_line=0.0, histogram=hist,
                               bullish_cross=bull, bearish_cross=False,
                               zero_cross_up=False, trend_strength=strength, score=50.0)

    def _hurst(self, interp):
        return SimpleNamespace(hurst=0.6 if interp == "TRENDING" else 0.35,
                               interpretation=interp, strategy_fit="", confidence="HIGH")

    def _mr(self, bb):
        return SimpleNamespace(zscore_20d=0.0, zscore_50d=0.0, bollinger_pct=bb,
                               is_oversold=False, is_overbought=False, signal_strength=0.0)

    def test_real_uptrend_is_buy_now(self):
        eq = compute_entry_quality(self._macd(1.0, "BULL", bull=True),
                                   self._hurst("TRENDING"), self._mr(0.5))
        assert eq.rating == "BUY_NOW" and eq.score >= 58

    def test_fake_momentum_is_avoid(self):
        # MACD up but Hurst mean-reverting → momentum will snap back.
        eq = compute_entry_quality(self._macd(1.0, "BULL"),
                                   self._hurst("MEAN_REVERTING"), self._mr(0.5))
        assert eq.rating == "AVOID" and eq.score < 42

    def test_overbought_uptrend_waits_for_dip(self):
        eq = compute_entry_quality(self._macd(1.0, "BULL"),
                                   self._hurst("TRENDING"), self._mr(0.98))
        assert eq.rating == "WAIT_PULLBACK"
        assert eq.bb_flag == "OVERBOUGHT"

    def test_score_and_rating_never_disagree(self):
        # BUY_NOW must score higher than AVOID — the two must stay consistent.
        buy = compute_entry_quality(self._macd(1.0, "BULL", bull=True),
                                    self._hurst("TRENDING"), self._mr(0.4))
        avoid = compute_entry_quality(self._macd(-1.0, "STRONG_BEAR"),
                                      self._hurst("TRENDING"), self._mr(0.5))
        assert buy.score > avoid.score
        assert 0 <= buy.score <= 100 and 0 <= avoid.score <= 100


# ── _compute_mean_reversion ───────────────────────────────────────────────────

class TestComputeMeanReversion:
    def test_signal_strength_in_range(self, trending_prices):
        result = _compute_mean_reversion(trending_prices)
        assert -1 <= result.signal_strength <= 1

    def test_booleans_are_bool(self, trending_prices):
        result = _compute_mean_reversion(trending_prices)
        assert isinstance(result.is_oversold, bool)
        assert isinstance(result.is_overbought, bool)

    def test_not_both_oversold_and_overbought(self, trending_prices):
        result = _compute_mean_reversion(trending_prices)
        assert not (result.is_oversold and result.is_overbought)


# ── _compute_statistical ──────────────────────────────────────────────────────

class TestComputeStatistical:
    def test_composite_score_in_range(self, trending_prices):
        result = _compute_statistical(trending_prices)
        assert 0 <= result.composite_score <= 100

    def test_signal_in_valid_set(self, trending_prices):
        result = _compute_statistical(trending_prices)
        assert result.signal in ("STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL")

    def test_sub_components_present(self, trending_prices):
        result = _compute_statistical(trending_prices)
        assert result.markov is not None
        assert result.kalman is not None
        assert result.hurst is not None
        assert result.mean_reversion is not None

    def test_flat_prices(self, flat_prices):
        result = _compute_statistical(flat_prices)
        assert 0 <= result.composite_score <= 100
        assert result.signal in ("STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL")


# ── build_quant_report ────────────────────────────────────────────────────────

class TestBuildQuantReport:
    def test_overall_score_in_range(self, trending_prices, ohlcv_df):
        sd = _make_stock_data("TEST")
        report = build_quant_report(sd, trending_prices, ohlcv_df)
        assert 0 <= report.overall_quant_score <= 100

    def test_signal_valid(self, trending_prices, ohlcv_df):
        sd = _make_stock_data("TEST")
        report = build_quant_report(sd, trending_prices, ohlcv_df)
        assert report.signal_type in ("STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL")

    def test_ticker_preserved(self, trending_prices, ohlcv_df):
        sd = _make_stock_data("NVDA")
        report = build_quant_report(sd, trending_prices, ohlcv_df)
        assert report.ticker == "NVDA"

    def test_thesis_contains_signal(self, trending_prices, ohlcv_df):
        sd = _make_stock_data("TEST")
        report = build_quant_report(sd, trending_prices, ohlcv_df)
        assert report.signal_type in report.quant_thesis

    def test_fallback_no_hist_df(self, trending_prices):
        """build_quant_report should work with hist_df=None (uses fallback)."""
        sd = _make_stock_data("TEST")
        report = build_quant_report(sd, trending_prices, hist_df=None)
        assert 0 <= report.overall_quant_score <= 100

    def test_etf_flag(self, trending_prices, ohlcv_df):
        sd = _make_stock_data("SPY")
        sd.is_etf = True
        report = build_quant_report(sd, trending_prices, ohlcv_df)
        assert 0 <= report.overall_quant_score <= 100


class TestQMJQuality:
    """AQR Quality Minus Junk — Profitability / Growth / Safety pillars."""

    def _sd(self, **over):
        base = dict(
            pe_ratio=20.0, pb_ratio=3.0, ps_ratio=5.0, forward_pe=18.0,
            revenue_growth=15.0, earnings_growth=20.0, profit_margin=18.0,
            return_1m=2.0, return_6m=10.0, return_1y=25.0, upside_to_target=12.0,
            return_on_equity=22.0, debt_to_equity=0.4,
        )
        base.update(over)
        return SimpleNamespace(**base)

    def test_pillars_populated_and_in_range(self):
        f = _compute_fundamental(self._sd())
        for p in (f.qmj_profitability, f.qmj_growth, f.qmj_safety):
            assert p is not None and 0 <= p <= 10
        assert 0 <= f.quality_score <= 10

    def test_quality_is_pillar_average(self):
        f = _compute_fundamental(self._sd())
        avg = round((f.qmj_profitability + f.qmj_growth + f.qmj_safety) / 3, 2)
        assert abs(f.quality_score - avg) < 0.01

    def test_high_quality_beats_junk(self):
        # Profitable, growing, low-leverage vs unprofitable, shrinking, levered.
        good = _compute_fundamental(self._sd(
            profit_margin=30.0, return_on_equity=35.0, earnings_growth=40.0,
            revenue_growth=35.0, debt_to_equity=0.2))
        junk = _compute_fundamental(self._sd(
            profit_margin=-5.0, return_on_equity=-10.0, earnings_growth=-20.0,
            revenue_growth=-10.0, debt_to_equity=4.0))
        assert good.quality_score > junk.quality_score
        assert good.qmj_safety > junk.qmj_safety

    def test_leverage_lowers_safety(self):
        low_lev = _compute_fundamental(self._sd(debt_to_equity=0.1))
        high_lev = _compute_fundamental(self._sd(debt_to_equity=3.5))
        assert low_lev.qmj_safety > high_lev.qmj_safety

    def test_missing_fields_still_scores(self):
        # No ROE / leverage available — should still return neutral-ish quality.
        sd = SimpleNamespace(
            pe_ratio=20.0, pb_ratio=3.0, ps_ratio=5.0, forward_pe=18.0,
            revenue_growth=None, earnings_growth=None, profit_margin=None,
            return_1m=0.0, return_6m=0.0, return_1y=0.0, upside_to_target=None)
        f = _compute_fundamental(sd)
        assert 0 <= f.quality_score <= 10


class TestSignalQualityFixes:
    def _sd(self, **over):
        base = dict(
            ticker="TEST", pe_ratio=20.0, pb_ratio=3.0, ps_ratio=5.0, forward_pe=18.0,
            revenue_growth=30.0, earnings_growth=20.0, profit_margin=18.0,
            return_1m=2.0, return_6m=10.0, return_1y=25.0, upside_to_target=12.0,
            return_on_equity=22.0, debt_to_equity=0.4, market_cap_b=50.0,
            is_etf=False, gem_category=None)
        base.update(over)
        return SimpleNamespace(**base)

    def test_microcap_extreme_growth_discounted(self):
        # +9000% rev growth on a $0.3B cap should score LOWER on growth than a
        # healthy +40% grower at a normal cap (noise guard).
        noisy = _compute_fundamental(self._sd(revenue_growth=9000.0, market_cap_b=0.3))
        real  = _compute_fundamental(self._sd(revenue_growth=40.0, market_cap_b=50.0))
        assert noisy.growth_score < real.growth_score

    def test_large_cap_extreme_growth_not_penalized(self):
        # Same +9000% but at a large cap is not treated as micro-cap noise.
        big = _compute_fundamental(self._sd(revenue_growth=9000.0, market_cap_b=50.0))
        assert big.growth_score >= 7.0

    def test_trending_growth_name_not_strong_sell(self, trending_prices, ohlcv_df):
        # A strong uptrending high-grower must not be tagged SELL/STRONG_SELL
        # purely because mean-reversion reads it as 'overbought'.
        sd = self._sd(revenue_growth=120.0, return_1y=95.0, market_cap_b=8.0)
        report = build_quant_report(sd, trending_prices, ohlcv_df)
        assert report.signal_type not in ("SELL", "STRONG_SELL")


class TestFactorArbitration:
    def _sd(self, **over):
        base = dict(
            ticker="TEST", pe_ratio=20.0, pb_ratio=3.0, ps_ratio=5.0, forward_pe=18.0,
            revenue_growth=10.0, earnings_growth=5.0, profit_margin=8.0,
            return_1m=2.0, return_6m=5.0, return_1y=10.0, upside_to_target=None,
            return_on_equity=12.0, debt_to_equity=0.8, market_cap_b=20.0,
            is_etf=False, gem_category=None)
        base.update(over)
        return SimpleNamespace(**base)

    def test_analyst_upside_lifts_score(self, flat_prices, ohlcv_df):
        low = build_quant_report(self._sd(upside_to_target=None), flat_prices, ohlcv_df)
        high = build_quant_report(self._sd(upside_to_target=40.0), flat_prices, ohlcv_df)
        assert high.overall_quant_score > low.overall_quant_score

    def _bearish(self):
        np.random.seed(11)
        rets = np.random.normal(-0.004, 0.02, 252)   # persistent downtrend
        px = pd.Series(100 * np.exp(np.cumsum(rets)))
        df = pd.DataFrame({"Close": px, "High": px * 1.005, "Low": px * 0.995,
                           "Volume": np.random.uniform(1e6, 1e7, len(px))})
        return px, df

    def test_analyst_more_bullish_than_model_is_flagged(self):
        px, df = self._bearish()
        sd = self._sd(upside_to_target=45.0, profit_margin=-5.0, revenue_growth=-5.0,
                      return_1y=-30.0, return_1m=-8.0)
        report = build_quant_report(sd, px, df)
        # Big analyst upside while the model is not a BUY → flagged as a conflict,
        # and never left in the SELL band (rescued to HOLD).
        assert "analyst" in report.signal_conflicts.lower()
        assert report.signal_type not in ("SELL", "STRONG_SELL")

    def test_timeframe_conflict_flagged(self):
        px, df = self._bearish()
        sd = self._sd(return_1m=12.0, return_1y=-40.0)   # 1M up, 1Y crashed (SMR-like)
        report = build_quant_report(sd, px, df)
        assert "timeframe" in report.signal_conflicts.lower()

    def test_no_conflict_when_aligned(self, trending_prices, ohlcv_df):
        sd = self._sd(return_1m=5.0, return_6m=20.0, return_1y=40.0,
                      revenue_growth=30.0, upside_to_target=20.0)
        report = build_quant_report(sd, trending_prices, ohlcv_df)
        # An aligned bullish name need not flag the analyst/timeframe conflicts.
        assert "analyst sees" not in report.signal_conflicts
