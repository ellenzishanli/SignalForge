"""
Risk Parity (Equal Risk Contribution) — the Bridgewater "All Weather" engine.

Where the Defensive Alpha engine (construction.py) sizes positions by *return*
quality (appraisal ratio) and then tilts for beta, Risk Parity ignores expected
return entirely and sizes by *risk* alone: every holding contributes the SAME
share of total portfolio volatility.

Why this matters (Bridgewater's insight, "The All Weather Story"): a 60/40
stock/bond book looks balanced by *dollars* but is ~90% equity risk — stocks are
~3-4× as volatile as bonds, so equities dominate the P&L and the bonds barely
matter in a crash. Equalizing *risk contribution* instead of dollars gives a far
smoother ride: low-vol assets (bonds, gold, defensives) get scaled UP, high-vol
assets (NVDA, leveraged growth) get scaled DOWN, until each carries its weight.

Math (Maillard, Roncalli & Teiletche 2010; Spinu 2013):
  - Marginal risk of asset i:  MRC_i = (Σw)_i / σ(w),   σ(w) = sqrt(w'Σw)
  - Risk contribution:         RC_i  = w_i · MRC_i,   and  Σ_i RC_i = σ(w)
  - Equal Risk Contribution:   RC_i = σ(w)/n  for all i.

We solve it with cyclical coordinate descent (Griveau-Billion, Richard &
Roncalli 2013): for each asset i in turn, hold the others fixed and solve the
1-D quadratic that sets RC_i to its target budget. It is robust, long-only by
construction, and converges in a handful of sweeps.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from portfolio.factor_model import FactorProfile, TRADING_DAYS
from portfolio.construction import Portfolio, Holding, _nz


def solve_risk_parity(
    cov: np.ndarray,
    budgets: Optional[np.ndarray] = None,
    max_iter: int = 500,
    tol: float = 1e-8,
) -> np.ndarray:
    """
    Equal (or custom budget) Risk Contribution weights via cyclical coordinate
    descent. ``cov`` is an n×n covariance matrix; returns long-only weights that
    sum to 1.

    Coordinate update for asset i (others fixed): with σ_ii the variance and
    α_i = Σ_{j≠i} cov_ij w_j the cross term, the target RC_i = b_i·σ² gives
        σ_ii·w_i² + α_i·w_i − b_i·σ² = 0
    whose positive root is the new w_i.
    """
    n = cov.shape[0]
    if budgets is None:
        budgets = np.full(n, 1.0 / n)
    budgets = budgets / budgets.sum()

    # Start from inverse-variance ("naive risk parity") — a good warm start.
    var = np.clip(np.diag(cov), 1e-12, None)
    w = (1.0 / var)
    w = w / w.sum()

    for _ in range(max_iter):
        w_prev = w.copy()
        sigma2 = float(w @ cov @ w)
        sigma = np.sqrt(max(sigma2, 1e-18))
        for i in range(n):
            alpha = float(cov[i] @ w) - cov[i, i] * w[i]   # cross term, excl. i
            a = cov[i, i]
            # Positive root of a·w² + alpha·w − b_i·σ² = 0
            disc = alpha * alpha + 4.0 * a * budgets[i] * sigma2
            w[i] = (-alpha + np.sqrt(max(disc, 0.0))) / (2.0 * a) if a > 1e-18 else 0.0
            w = w / w.sum()                                # renormalize each step
            sigma2 = float(w @ cov @ w)
            sigma = np.sqrt(max(sigma2, 1e-18))
        if np.max(np.abs(w - w_prev)) < tol:
            break

    return np.clip(w, 0.0, None) / np.clip(w, 0.0, None).sum()


def risk_contributions(weights: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """Fractional risk contribution of each asset (sums to 1)."""
    sigma2 = float(weights @ cov @ weights)
    if sigma2 <= 0:
        return np.full(len(weights), 1.0 / len(weights))
    rc = weights * (cov @ weights) / np.sqrt(sigma2)
    total = rc.sum()
    return rc / total if total else rc


def build_risk_parity_portfolio(
    profiles: List[FactorProfile],
    prices: Dict[str, pd.Series],
    max_weight: float = 0.25,
) -> Portfolio:
    """
    Construct an Equal-Risk-Contribution book over every name we have a factor
    profile for, using the sample covariance of daily returns. Returns the same
    ``Portfolio`` object the Defensive engine produces, so the existing stress
    test and display code work unchanged.

    ``target_beta`` on the returned Portfolio is repurposed to carry the achieved
    portfolio beta (risk parity has no beta *target* — beta is an output).
    """
    # Align daily returns across all names that have both a profile and prices.
    cols = {}
    for p in profiles:
        s = prices.get(p.ticker)
        if s is not None:
            cols[p.ticker] = s.pct_change()
    rets = pd.DataFrame(cols).dropna()
    if rets.shape[1] < 2 or len(rets) < 60:
        # Degenerate: fall back to equal weight.
        tickers = list(cols.keys())
        w = {t: 1.0 / len(tickers) for t in tickers} if tickers else {}
    else:
        cov = rets.cov().values * TRADING_DAYS      # annualized; scale-invariant anyway
        tickers = list(rets.columns)
        weights = solve_risk_parity(cov)
        weights = _cap_and_renorm_rp(dict(zip(tickers, weights)), cov, tickers, max_weight)
        w = weights

    prof_by_ticker = {p.ticker: p for p in profiles}
    holdings: List[Holding] = []
    for t, wt in w.items():
        if wt > 0.0005 and t in prof_by_ticker:
            holdings.append(Holding(prof_by_ticker[t], round(float(wt), 4)))
    holdings.sort(key=lambda h: h.weight, reverse=True)

    invested = sum(h.weight for h in holdings)
    cash = max(0.0, 1.0 - invested)
    port_beta = sum(h.weight * h.profile.beta_lagged for h in holdings)
    port_dbeta = sum(h.weight * _nz(h.profile.downside_beta) for h in holdings)
    port_ubeta = sum(h.weight * _nz(h.profile.upside_beta) for h in holdings)
    port_alpha = sum(h.weight * h.profile.alpha_annual for h in holdings)
    port_appr = sum(h.weight * h.profile.appraisal_ratio for h in holdings)

    sleeve_w: Dict[str, float] = {}
    for h in holdings:
        sleeve_w[h.profile.sleeve] = sleeve_w.get(h.profile.sleeve, 0.0) + h.weight
    if cash > 0.0005:
        sleeve_w["cash"] = cash

    return Portfolio(
        holdings=holdings, cash_weight=round(cash, 4),
        target_beta=round(port_beta, 3),           # achieved beta (no target here)
        port_beta=round(port_beta, 3), port_downside_beta=round(port_dbeta, 3),
        port_upside_beta=round(port_ubeta, 3), port_alpha_annual=round(port_alpha, 2),
        port_appraisal=round(port_appr, 3),
        sleeve_weights={k: round(v, 4) for k, v in sleeve_w.items()},
    )


def _cap_and_renorm_rp(
    weights: Dict[str, float], cov: np.ndarray, tickers: List[str], cap: float
) -> Dict[str, float]:
    """Apply a per-name cap, then re-solve ERC on the uncapped names so the
    risk-balance property is preserved among the names still free to move."""
    w = dict(weights)
    capped = {k for k, v in w.items() if v > cap}
    if not capped:
        return w
    for _ in range(5):
        free = [t for t in tickers if t not in capped]
        if not free:
            break
        fixed_w = sum(cap for _ in capped)
        budget_free = max(1e-9, 1.0 - fixed_w)
        idx = [tickers.index(t) for t in free]
        sub = cov[np.ix_(idx, idx)]
        sub_w = solve_risk_parity(sub) * budget_free
        for k in capped:
            w[k] = cap
        for t, sw in zip(free, sub_w):
            w[t] = float(sw)
        new_over = {t for t in free if w[t] > cap + 1e-9}
        if not new_over:
            break
        capped |= new_over
    total = sum(w.values())
    return {k: v / total for k, v in w.items()} if total else w
