"""
Beta-Adjusted Alpha — the CAPM factor model behind SignalForge's defensive engine.

The question this answers: "Of a stock's return, how much is just the market (beta)
that I could get for free from an index fund, and how much is genuine, unique skill-
or-thesis-driven excess return (alpha)?" Only the alpha improves a diversified
portfolio — and alpha is only worth holding if it is large *relative to the
idiosyncratic risk* you take to get it. That ratio is the appraisal ratio.

Grounded in AQR's "Total Portfolio Approach" (2026): the appraisal ratio =
alpha / residual-volatility is the right way to rank investments for inclusion,
and portfolio weights should be proportional to it.

Key estimates per name:
  beta            — standard CAPM market beta (OLS of excess return on excess market)
  beta_lagged     — Dimson/Asness beta: contemporaneous + lagged market betas summed.
                    Catches the "true" beta of names whose price reacts with a delay
                    (Asness's point about understated betas from illiquidity/smoothing).
  alpha_annual    — Jensen's alpha, annualized (the regression intercept × 252)
  appraisal_ratio — alpha_annual / idiosyncratic-vol — beta-adjusted alpha quality
  downside_beta   — beta measured only on down-market days (what hurts you in a crash)
  upside_beta     — beta measured only on up-market days (what you keep in a rally)
  convexity       — upside_beta − downside_beta. POSITIVE = good asymmetry: participates
                    on the way up, protects on the way down. This is the holy grail.
"""
from dataclasses import dataclass
from typing import Optional
import numpy as np
import pandas as pd

# Default annual risk-free rate for excess-return / CAPM regressions.
DEFAULT_RF_ANNUAL = 0.043
TRADING_DAYS = 252


@dataclass
class FactorProfile:
    ticker: str
    name: str
    sleeve: str                # alpha | defensive | convexity
    n_obs: int                 # number of aligned daily observations
    beta: float
    beta_lagged: float         # Dimson beta — true market sensitivity
    alpha_annual: float        # Jensen's alpha, % per year
    idio_vol_annual: float     # idiosyncratic (residual) volatility, % per year
    appraisal_ratio: float     # alpha / idio vol — the beta-adjusted alpha score
    r_squared: float           # fraction of variance explained by the market
    total_vol_annual: float    # standalone volatility, % per year
    corr_market: float
    downside_beta: float
    upside_beta: float
    convexity: float           # upside_beta − downside_beta
    ann_return: float          # realized annualized return over the window, %
    # ── Multi-factor (Fama-French via ETF proxies); None if not computed ──────
    alpha_mf_annual: Optional[float] = None    # alpha after stripping ALL factors
    r_squared_mf: Optional[float] = None       # multi-factor R² (much higher than CAPM)
    beta_mkt_mf: Optional[float] = None        # market loading in the MF model
    beta_size: Optional[float] = None          # SMB loading
    beta_value: Optional[float] = None         # HML loading (+ = value, − = growth)
    beta_mom: Optional[float] = None           # MOM loading
    beta_qual: Optional[float] = None          # QMJ loading
    idio_vol_mf_annual: Optional[float] = None # residual vol after ALL factors, %/yr
    appraisal_mf: Optional[float] = None       # MF alpha / MF residual vol (honest appraisal)


def _ols(y: np.ndarray, X: np.ndarray):
    """Ordinary least squares. X already includes an intercept column. Returns (coefs, residuals)."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        coefs, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ coefs
    return coefs, resid


def compute_factor_profile(
    ticker: str,
    name: str,
    sleeve: str,
    stock_prices: pd.Series,
    market_prices: pd.Series,
    rf_annual: float = DEFAULT_RF_ANNUAL,
    factors: Optional[pd.DataFrame] = None,
) -> Optional[FactorProfile]:
    """
    Estimate the full CAPM factor profile for one name vs the market (SPY).
    Prices are aligned on their common dates; needs >= ~120 overlapping days.

    If ``factors`` (a daily DataFrame of Fama-French style factor returns, see
    portfolio/factors.py) is supplied, also run the multi-factor regression and
    fill the MF fields (multi-factor alpha, R², and per-factor loadings).
    """
    # Align on common dates, convert to daily simple returns.
    df = pd.concat([stock_prices.rename("s"), market_prices.rename("m")], axis=1).dropna()
    if len(df) < 120:
        return None
    rs = df["s"].pct_change().dropna()
    rm = df["m"].pct_change().dropna()
    common = rs.index.intersection(rm.index)
    rs, rm = rs.loc[common], rm.loc[common]
    if len(rs) < 120:
        return None

    rf_daily = rf_annual / TRADING_DAYS
    ys = rs.values - rf_daily          # excess stock return
    xm = rm.values - rf_daily          # excess market return
    n = len(ys)

    # ── Standard CAPM: r_excess = alpha + beta * mkt_excess ──────────────────
    X = np.column_stack([np.ones(n), xm])
    coefs, resid = _ols(ys, X)
    alpha_daily, beta = coefs[0], coefs[1]
    idio_vol_daily = float(np.std(resid, ddof=2))
    total_vol_daily = float(np.std(ys, ddof=1))
    r2 = 1.0 - np.var(resid) / np.var(ys) if np.var(ys) > 0 else 0.0
    corr = float(np.corrcoef(rs.values, rm.values)[0, 1])

    # ── Dimson/Asness lagged beta: add yesterday's market return ─────────────
    # True beta = sum of contemporaneous + lagged coefficients. Reveals names
    # whose price digests market moves with a delay (understated by plain OLS).
    xm_lag = np.concatenate([[0.0], xm[:-1]])
    Xl = np.column_stack([np.ones(n), xm, xm_lag])
    coefs_l, _ = _ols(ys, Xl)
    beta_lagged = float(coefs_l[1] + coefs_l[2])

    # ── Downside vs upside beta (convexity) ──────────────────────────────────
    down = xm < 0
    up = xm > 0
    downside_beta = _conditional_beta(ys[down], xm[down])
    upside_beta = _conditional_beta(ys[up], xm[up])
    convexity = upside_beta - downside_beta

    # ── Annualize ────────────────────────────────────────────────────────────
    alpha_annual = alpha_daily * TRADING_DAYS * 100
    idio_vol_annual = idio_vol_daily * np.sqrt(TRADING_DAYS) * 100
    total_vol_annual = total_vol_daily * np.sqrt(TRADING_DAYS) * 100
    appraisal = (alpha_annual / idio_vol_annual) if idio_vol_annual > 1e-9 else 0.0
    ann_return = (float(np.mean(rs.values)) * TRADING_DAYS) * 100

    # ── Multi-factor (Fama-French style) regression, if factors provided ──────
    mf = _multifactor_fit(rs, factors, rf_daily) if factors is not None else None

    return FactorProfile(
        ticker=ticker, name=name, sleeve=sleeve, n_obs=n,
        beta=round(beta, 3), beta_lagged=round(beta_lagged, 3),
        alpha_annual=round(alpha_annual, 2),
        idio_vol_annual=round(idio_vol_annual, 1),
        appraisal_ratio=round(appraisal, 3),
        r_squared=round(float(r2), 3),
        total_vol_annual=round(total_vol_annual, 1),
        corr_market=round(corr, 3),
        downside_beta=round(downside_beta, 3),
        upside_beta=round(upside_beta, 3),
        convexity=round(convexity, 3),
        ann_return=round(ann_return, 1),
        **(mf or {}),
    )


def _multifactor_fit(rs: pd.Series, factors: pd.DataFrame, rf_daily: float) -> Optional[dict]:
    """
    Regress the stock's excess daily return on the factor matrix
    (mkt, smb, hml, mom, qmj). Returns a dict of MF fields, or None if there is
    too little overlap. Strips the *known* factor exposures so the residual alpha
    is far more honest than the single-SPY version.
    """
    from portfolio.factors import FACTOR_COLUMNS
    cols = [c for c in FACTOR_COLUMNS if c in factors.columns]
    if not cols:
        return None
    df = pd.concat([rs.rename("y"), factors[cols]], axis=1).dropna()
    if len(df) < 120:
        return None
    y = df["y"].values - rf_daily
    X = np.column_stack([np.ones(len(df))] + [df[c].values for c in cols])
    coefs, resid = _ols(y, X)
    r2 = 1.0 - np.var(resid) / np.var(y) if np.var(y) > 0 else 0.0
    loadings = dict(zip(cols, coefs[1:]))
    alpha_mf_annual = float(coefs[0]) * TRADING_DAYS * 100
    idio_vol_mf_annual = float(np.std(resid, ddof=len(cols) + 1)) * np.sqrt(TRADING_DAYS) * 100
    appraisal_mf = (alpha_mf_annual / idio_vol_mf_annual) if idio_vol_mf_annual > 1e-9 else 0.0
    out = {
        "alpha_mf_annual": round(alpha_mf_annual, 2),
        "r_squared_mf": round(float(r2), 3),
        "beta_mkt_mf": round(float(loadings.get("mkt", float("nan"))), 3),
        "beta_size": round(float(loadings.get("smb", float("nan"))), 3),
        "beta_value": round(float(loadings.get("hml", float("nan"))), 3),
        "beta_mom": round(float(loadings.get("mom", float("nan"))), 3),
        "beta_qual": round(float(loadings.get("qmj", float("nan"))), 3),
        "idio_vol_mf_annual": round(idio_vol_mf_annual, 1),
        "appraisal_mf": round(appraisal_mf, 3),
    }
    return out


def _conditional_beta(y: np.ndarray, x: np.ndarray) -> float:
    """Beta estimated on a subset of days (e.g., only down-market days)."""
    if len(x) < 20 or np.var(x) < 1e-12:
        return float("nan")
    # Simple covariance/variance beta on the conditional sample.
    return float(np.cov(y, x, ddof=1)[0, 1] / np.var(x, ddof=1))
