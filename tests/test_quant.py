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
