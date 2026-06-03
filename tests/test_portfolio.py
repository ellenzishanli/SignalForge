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
from portfolio.factors import build_factor_returns, factor_proxy_tickers, FACTOR_COLUMNS
from portfolio.construction import construct_defensive_portfolio
from portfolio.risk_parity import (
    solve_risk_parity, risk_contributions, build_risk_parity_portfolio,
)


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


class TestMultiFactor:
    def _factor_prices(self, n=600, seed=20):
        """Synthetic price series for SPY + the factor-proxy ETFs."""
        rng = np.random.default_rng(seed)
        idx = pd.bdate_range("2021-01-01", periods=n)
        prices = {}
        for t in factor_proxy_tickers():
            ret = rng.normal(0.0003, 0.01, n)
            prices[t] = pd.Series(100 * np.cumprod(1 + ret), index=idx)
        return prices, idx

    def test_build_factor_returns_has_columns(self):
        prices, _ = self._factor_prices()
        f = build_factor_returns(prices)
        assert f is not None
        for c in FACTOR_COLUMNS:
            assert c in f.columns

    def test_build_factor_returns_none_without_spy(self):
        prices, _ = self._factor_prices()
        prices.pop("SPY")
        assert build_factor_returns(prices) is None

    def test_multifactor_fields_populated(self):
        prices, idx = self._factor_prices()
        factors = build_factor_returns(prices)
        # Build a stock that is mostly market + momentum exposure.
        rng = np.random.default_rng(99)
        spy_ret = prices["SPY"].pct_change().fillna(0).values
        mom_ret = (prices["MTUM"].pct_change().fillna(0).values
                   - prices["SPY"].pct_change().fillna(0).values)
        stock_ret = 1.3 * spy_ret + 0.8 * mom_ret + rng.normal(0, 0.004, len(idx))
        stock_px = pd.Series(100 * np.cumprod(1 + stock_ret), index=idx)
        p = compute_factor_profile("X", "Test", "alpha", stock_px, prices["SPY"], factors=factors)
        assert p is not None
        assert p.alpha_mf_annual is not None
        assert p.r_squared_mf is not None
        assert p.beta_mom is not None
        # Multi-factor R² should explain a meaningful share of variance.
        assert p.r_squared_mf > 0.5

    def test_no_factors_leaves_mf_none(self):
        stk, mkt = _make_series(beta=1.0, alpha_daily=0.0, noise=0.004, seed=5)
        p = compute_factor_profile("X", "Test", "alpha", stk, mkt)  # no factors
        assert p.alpha_mf_annual is None
        assert p.r_squared_mf is None


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


class TestRiskParity:
    def test_equalizes_risk_contributions(self):
        # Uncorrelated assets with very different variances: ERC must equalize RC.
        cov = np.diag([0.04, 0.01, 0.0025])      # vols 20%, 10%, 5%
        w = solve_risk_parity(cov)
        assert abs(w.sum() - 1.0) < 1e-9
        rc = risk_contributions(w, cov)
        assert np.max(np.abs(rc - 1.0 / len(w))) < 1e-3

    def test_low_vol_gets_more_weight(self):
        # For uncorrelated assets, ERC weight should be inverse to volatility.
        cov = np.diag([0.04, 0.01])              # asset 0 is 2× the vol of asset 1
        w = solve_risk_parity(cov)
        assert w[1] > w[0]                         # lower-vol asset carries more weight

    def test_handles_correlation(self):
        cov = np.array([[0.04, 0.012], [0.012, 0.01]])  # correlated, PSD
        w = solve_risk_parity(cov)
        rc = risk_contributions(w, cov)
        assert np.max(np.abs(rc - 0.5)) < 1e-3
        assert (w >= 0).all()

    def _profiles_and_prices(self):
        profs, prices = [], {}
        specs = [
            ("HIVOL", "alpha", 1.6, 0.0003, 0.020, 11),   # high idiosyncratic vol
            ("MIDVOL", "alpha", 1.0, 0.0002, 0.010, 12),
            ("LOVOL", "defensive", 0.4, 0.0001, 0.004, 13),  # low vol ballast
            ("HEDGE", "convexity", -0.5, 0.0, 0.006, 14),
        ]
        for tk, slv, beta, a, noise, seed in specs:
            stk, mkt = _make_series(beta=beta, alpha_daily=a, noise=noise, seed=seed)
            p = compute_factor_profile(tk, tk, slv, stk, mkt)
            assert p is not None
            profs.append(p)
            prices[tk] = stk
        return profs, prices

    def test_build_portfolio_weights_sum_to_one(self):
        profs, prices = self._profiles_and_prices()
        port = build_risk_parity_portfolio(profs, prices)
        total = sum(h.weight for h in port.holdings) + port.cash_weight
        assert abs(total - 1.0) < 0.02
        assert all(h.weight >= 0 for h in port.holdings)

    def test_build_portfolio_favors_low_vol(self):
        profs, prices = self._profiles_and_prices()
        # Loose cap so the risk-balance tilt is visible (with only 4 names a 25%
        # cap would force equal weight: 4 × 25% = 100%).
        port = build_risk_parity_portfolio(profs, prices, max_weight=0.6)
        w = {h.profile.ticker: h.weight for h in port.holdings}
        # The lowest-vol name should out-weight the highest-vol name.
        assert w.get("LOVOL", 0) > w.get("HIVOL", 0)
