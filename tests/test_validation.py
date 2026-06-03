"""
Unit tests for the predictive-power validation suite (rank IC + quantiles).
Synthetic panels so the tests are deterministic and offline.
"""
import sys, os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from stocks.backtest import compute_period_ic, compute_quantile_performance


def _panel(n_dates=8, n_names=20, signal_strength=0.0, seed=0):
    """Build a (date, ticker, composite, fwd_ret) panel. signal_strength controls
    how strongly the score predicts the forward return (0 = pure noise)."""
    rng = np.random.default_rng(seed)
    rows = []
    for d in range(n_dates):
        scores = rng.normal(50, 15, n_names)
        noise = rng.normal(0, 8, n_names)
        # forward return = signal_strength * (centered score) + noise
        fwd = signal_strength * (scores - 50) + noise
        for i in range(n_names):
            rows.append({"eval_date": f"2025-{d+1:02d}-01", "ticker": f"T{i}",
                         "composite": scores[i], "fwd_ret": fwd[i]})
    return pd.DataFrame(rows)


class TestPeriodIC:
    def test_predictive_score_has_positive_ic(self):
        df = _panel(signal_strength=0.6, seed=1)
        ic = compute_period_ic(df)
        assert ic["mean_ic"] > 0.2
        assert ic["pct_positive"] > 60
        assert ic["n_periods"] == 8

    def test_random_score_has_near_zero_ic(self):
        df = _panel(signal_strength=0.0, seed=2)
        ic = compute_period_ic(df)
        assert abs(ic["mean_ic"]) < 0.2          # no real edge

    def test_empty_panel_is_safe(self):
        ic = compute_period_ic(pd.DataFrame(columns=["eval_date", "composite", "fwd_ret"]))
        assert ic["n_periods"] == 0
        assert ic["mean_ic"] != ic["mean_ic"]    # NaN


class TestQuantilePerformance:
    def test_predictive_score_is_monotonic_with_positive_spread(self):
        df = _panel(signal_strength=0.8, seed=3)
        q = compute_quantile_performance(df, n_buckets=5)
        assert q["long_short_spread"] > 0
        assert q["monotonic"] is True
        assert len(q["bucket_means"]) == 5

    def test_random_score_small_spread(self):
        df = _panel(signal_strength=0.0, seed=4)
        q = compute_quantile_performance(df, n_buckets=5)
        # With no signal the top-minus-bottom spread should be small.
        assert abs(q["long_short_spread"]) < 5.0
