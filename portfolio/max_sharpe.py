"""
Maximum-Sharpe (tangency) portfolio — the return-seeking construction method.

Defensive Alpha targets a low beta and Risk Parity ignores return entirely; both
deliberately leave return on the table. This method does the opposite: it finds
the long-only mix with the highest risk-adjusted *return* (Sharpe ratio), so it
sits much higher on the efficient frontier.

Two design choices keep it honest:

  • Expected returns are NOT raw historical means (which are noisy and overfit the
    2021-2026 AI bull run). Each name's expected return is rebuilt from its factor
    profile:   E[r] = rf + Dimson-beta · equity-risk-premium + haircut · alpha.
    The alpha is haircut 50% by default because individual-stock alpha mean-reverts
    (its out-of-sample persistence is weak) — so we don't bet the book on it.

  • The objective is return-seeking, so negative-carry "insurance" (TLT's ≈ −10%/yr,
    BTAL's bleed) gets ~zero weight automatically — no special-casing needed. That
    is the "make the convexity sleeve return-aware" fix, falling out of the math.

Long-only tangency is solved by the classic active-set method: compute the
unconstrained tangency weights ∝ Σ⁻¹(μ − rf), drop any name that wants a negative
weight, and re-solve on the survivors until all weights are non-negative.
"""
from typing import Dict, List
import numpy as np
import pandas as pd

from portfolio.factor_model import FactorProfile, TRADING_DAYS, DEFAULT_RF_ANNUAL
from portfolio.construction import Portfolio, Holding, _nz, _cap_and_renorm

DEFAULT_ERP = 0.05            # equity risk premium assumption
DEFAULT_ALPHA_HAIRCUT = 0.5   # trust only half of historical alpha (it mean-reverts)


def expected_return(profile: FactorProfile, rf: float = DEFAULT_RF_ANNUAL,
                    erp: float = DEFAULT_ERP, alpha_haircut: float = DEFAULT_ALPHA_HAIRCUT) -> float:
    """Forward expected annual return (decimal) rebuilt from the factor profile."""
    beta = profile.beta_lagged if profile.beta_lagged == profile.beta_lagged else profile.beta
    beta = beta if beta == beta else 1.0
    alpha = (profile.alpha_annual or 0.0) / 100.0
    return rf + beta * erp + alpha_haircut * alpha


def solve_max_sharpe(mu: np.ndarray, cov: np.ndarray, rf: float,
                     max_weight: float = 0.20) -> np.ndarray:
    """
    Long-only tangency weights via the active-set method. ``mu`` is the vector of
    expected annual returns, ``cov`` the annualized covariance matrix.
    """
    n = len(mu)
    active = np.ones(n, dtype=bool)
    w = np.full(n, 1.0 / n)
    excess_all = mu - rf

    for _ in range(n + 1):
        idx = np.where(active)[0]
        if len(idx) == 0:
            break
        sub_cov = cov[np.ix_(idx, idx)]
        sub_ex = excess_all[idx]
        raw = np.linalg.pinv(sub_cov) @ sub_ex
        if raw.sum() <= 0:
            # No positive-Sharpe combination — fall back to the positive-excess names.
            pos = excess_all > 0
            w = np.where(pos, excess_all, 0.0)
            w = w / w.sum() if w.sum() > 0 else np.full(n, 1.0 / n)
            return w
        sub_w = raw / raw.sum()
        if (sub_w >= -1e-9).all():
            w = np.zeros(n)
            w[idx] = np.clip(sub_w, 0.0, None)
            w = w / w.sum()
            break
        # Drop the names that want a short position and re-solve.
        for j, wj in zip(idx, sub_w):
            if wj < 0:
                active[j] = False

    # Apply a per-name cap and renormalize.
    capped = _cap_and_renorm({i: w[i] for i in range(n) if w[i] > 0}, max_weight)
    out = np.zeros(n)
    for i, wv in capped.items():
        out[i] = wv
    return out


def build_max_sharpe_portfolio(
    profiles: List[FactorProfile], prices: Dict[str, pd.Series],
    rf: float = DEFAULT_RF_ANNUAL, erp: float = DEFAULT_ERP,
    alpha_haircut: float = DEFAULT_ALPHA_HAIRCUT, max_weight: float = 0.20,
) -> Portfolio:
    """Construct the long-only maximum-Sharpe book. Returns the shared Portfolio
    object so the existing stress test and display work unchanged."""
    cols = {}
    for p in profiles:
        s = prices.get(p.ticker)
        if s is not None:
            cols[p.ticker] = s.pct_change()
    rets = pd.DataFrame(cols).dropna()

    prof_by_ticker = {p.ticker: p for p in profiles}
    if rets.shape[1] < 2 or len(rets) < 60:
        tickers = list(cols.keys())
        weights = {t: 1.0 / len(tickers) for t in tickers} if tickers else {}
    else:
        tickers = list(rets.columns)
        cov = rets.cov().values * TRADING_DAYS
        mu = np.array([expected_return(prof_by_ticker[t], rf, erp, alpha_haircut) for t in tickers])
        w_arr = solve_max_sharpe(mu, cov, rf, max_weight=max_weight)
        weights = {t: float(w) for t, w in zip(tickers, w_arr)}

    holdings: List[Holding] = []
    for t, wt in weights.items():
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
        target_beta=round(port_beta, 3),       # achieved beta (max-Sharpe has no beta target)
        port_beta=round(port_beta, 3), port_downside_beta=round(port_dbeta, 3),
        port_upside_beta=round(port_ubeta, 3), port_alpha_annual=round(port_alpha, 2),
        port_appraisal=round(port_appr, 3),
        sleeve_weights={k: round(v, 4) for k, v in sleeve_w.items()},
    )
