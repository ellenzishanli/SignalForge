"""
Unit tests for the technical analysis engine (stocks/technical.py).
"""
import sys
import os
import pytest
import numpy as np
import pandas as pd

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from stocks.technical import compute_technical_score


# ── compute_technical_score ───────────────────────────────────────────────────

class TestComputeTechnicalScore:
    def test_composite_score_in_range(self, ohlcv_df):
        closes = ohlcv_df["Close"]
        result = compute_technical_score(closes, ohlcv_df)
        assert 0 <= result.composite_score <= 100

    def test_signal_in_valid_set(self, ohlcv_df):
        closes = ohlcv_df["Close"]
        result = compute_technical_score(closes, ohlcv_df)
        assert result.signal in ("STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL")

    def test_macd_bullish_cross_is_bool(self, ohlcv_df):
        closes = ohlcv_df["Close"]
        result = compute_technical_score(closes, ohlcv_df)
        assert isinstance(result.macd.bullish_cross, bool)

    def test_stochastic_k_in_range(self, ohlcv_df):
        closes = ohlcv_df["Close"]
        result = compute_technical_score(closes, ohlcv_df)
        assert 0 <= result.stochastic.k_pct <= 100

    def test_minimal_data_no_raise(self):
        """Should work (or fall back gracefully) on a minimal 30-bar series."""
        np.random.seed(99)
        prices = pd.Series(100 * np.exp(np.cumsum(np.random.normal(0.001, 0.015, 30))))
        df = pd.DataFrame({
            "Close":  prices,
            "High":   prices * 1.005,
            "Low":    prices * 0.995,
            "Volume": np.random.uniform(1e6, 1e7, len(prices)),
        })
        result = compute_technical_score(prices, df)
        assert 0 <= result.composite_score <= 100

    def test_technical_thesis_not_empty(self, ohlcv_df):
        closes = ohlcv_df["Close"]
        result = compute_technical_score(closes, ohlcv_df)
        assert len(result.technical_thesis) > 0

    def test_flat_prices_no_raise(self, flat_prices):
        """Flat prices (no trend) should not raise."""
        df = pd.DataFrame({
            "Close":  flat_prices,
            "High":   flat_prices * 1.002,
            "Low":    flat_prices * 0.998,
            "Volume": np.random.uniform(1e6, 1e7, len(flat_prices)),
        })
        result = compute_technical_score(flat_prices, df)
        assert 0 <= result.composite_score <= 100

    def test_adx_score_in_range(self, ohlcv_df):
        closes = ohlcv_df["Close"]
        result = compute_technical_score(closes, ohlcv_df)
        assert 0 <= result.adx.score <= 100

    def test_all_sub_indicators_present(self, ohlcv_df):
        closes = ohlcv_df["Close"]
        result = compute_technical_score(closes, ohlcv_df)
        assert result.macd is not None
        assert result.stochastic is not None
        assert result.atr is not None
        assert result.obv is not None
        assert result.fibonacci is not None
        assert result.adx is not None
