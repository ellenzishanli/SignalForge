"""
Unit tests for the defensive portfolio engine — factor model + construction.
Uses synthetic price series so the tests are deterministic and offline.
"""
import numpy as np
import pandas as pd
import pytest

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from portfolio.factor_model import compute_factor_profile
from portfolio.construction import construct_defensive_portfolio


def _make_series(n=600, seed=0, beta=1.0, alpha_daily=0.0, noise=0.01):
    """Build a market series and a stock = alpha + beta*market + noise."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2021-01-01", periods=n)
    mkt_ret = rng.normal(0.0004, 0.01, n)
    stock_ret = alpha_daily + beta * mkt_ret + rng.normal(0, noise, n)
    mkt_px = pd.Series(100 * np.cumprod(1 + mkt_ret), index=idx)
    stk_px = pd.Series(100 * np.cumprod(1 + stock_ret), index=idx)
    return stk_px, mkt_px


class TestFactorModel:
    def test_recovers_known_beta(self):
        stk, mkt = _make_series(beta=1.5, alpha_daily=0.0, noise=0.003, seed=1)
        p = compute_factor_profile("X", "Test", "alpha", stk, mkt)
        assert p is not None
        # Beta should be recovered close to the true 1.5
        assert abs(p.beta - 1.5) < 0.15

    def test_recovers_positive_alpha(self):
        # 0.0004/day ≈ ~10%/yr alpha
        stk, mkt = _make_series(beta=1.0, alpha_daily=0.0004, noise=0.003, seed=2)
        p = compute_factor_profile("X", "Test", "alpha", stk, mkt)
        assert p.alpha_annual > 0
        assert p.appraisal_ratio > 0

    def test_low_beta_name_has_low_beta(self):
        stk, mkt = _make_series(beta=0.2, alpha_daily=0.0, noise=0.003, seed=3)
        p = compute_factor_profile("X", "Test", "defensive", stk, mkt)
        assert p.beta < 0.5

    def test_insufficient_data_returns_none(self):
        stk, mkt = _make_series(n=50)
        assert compute_factor_profile("X", "Test", "alpha", stk, mkt) is None

    def test_appraisal_ratio_sign_matches_alpha(self):
        stk, mkt = _make_series(beta=1.0, alpha_daily=-0.0004, noise=0.003, seed=4)
        p = compute_factor_profile("X", "Test", "alpha", stk, mkt)
        assert p.alpha_annual < 0
        assert p.appraisal_ratio < 0


class TestConstruction:
    def _profiles(self):
        """Three alpha names (varying beta/appraisal) + one negative-beta convex hedge."""
        profs = []
        specs = [
            ("HIGHA", "alpha", 1.5, 0.0005, 0.004, 5),
            ("MIDA",  "alpha", 1.0, 0.0003, 0.004, 6),
            ("LOWB",  "defensive", 0.4, 0.0002, 0.004, 7),
            ("HEDGE", "convexity", -0.6, 0.0, 0.004, 8),
        ]
        for tk, slv, beta, a, noise, seed in specs:
            stk, mkt = _make_series(beta=beta, alpha_daily=a, noise=noise, seed=seed)
            p = compute_factor_profile(tk, tk, slv, stk, mkt)
            assert p is not None
            profs.append(p)
        return profs

    def test_weights_sum_to_one(self):
        port = construct_defensive_portfolio(self._profiles(), target_beta=0.6)
        total = sum(h.weight for h in port.holdings) + port.cash_weight
        assert abs(total - 1.0) < 0.02

    def test_hits_target_beta(self):
        port = construct_defensive_portfolio(self._profiles(), target_beta=0.6)
        # Achieved beta should be at or below target (defensive).
        assert port.port_beta <= 0.6 + 0.1

    def test_no_negative_weights(self):
        port = construct_defensive_portfolio(self._profiles(), target_beta=0.6)
        assert all(h.weight >= 0 for h in port.holdings)

    def test_lower_target_beta_reduces_beta(self):
        profs = self._profiles()
        hi = construct_defensive_portfolio(profs, target_beta=0.8)
        lo = construct_defensive_portfolio(profs, target_beta=0.3)
        assert lo.port_beta <= hi.port_beta + 0.05
