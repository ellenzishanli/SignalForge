"""
Convexity & drawdown stress testing.

Given the constructed portfolio and the underlying price histories, build the
portfolio's daily return series and measure how it behaves specifically when the
market falls — the whole point of the exercise:

  downside_capture — avg portfolio return on down-SPY days ÷ avg SPY return on
                     those days. 0.6 means you only take 60% of the market's pain.
  upside_capture   — same on up days. You want this HIGH while downside stays LOW.
  capture_ratio    — upside ÷ downside. > 1 means favorable asymmetry (convexity).
  win_rate_down    — % of down-SPY months the portfolio still beat SPY.
  max_drawdown     — worst peak-to-trough, portfolio vs SPY.
  stress windows   — cumulative return through named historical selloffs.
"""
from dataclasses import dataclass, field
from typing import Dict, List
import numpy as np
import pandas as pd

from portfolio.construction import Portfolio


# Named historical stress windows (only used if the data window covers them).
STRESS_WINDOWS = {
    "2022 Inflation Bear": ("2022-01-01", "2022-10-12"),
    "2025 Tariff Shock":   ("2025-02-19", "2025-04-08"),
}


@dataclass
class StressReport:
    downside_capture: float
    upside_capture: float
    capture_ratio: float
    win_rate_down_months: float
    port_max_drawdown: float
    spy_max_drawdown: float
    port_ann_return: float
    spy_ann_return: float
    port_ann_vol: float
    spy_ann_vol: float
    port_sharpe: float
    spy_sharpe: float
    stress_windows: Dict[str, Dict[str, float]] = field(default_factory=dict)


def _portfolio_returns(port: Portfolio, prices: Dict[str, pd.Series]) -> pd.DataFrame:
    """Build a daily-return frame of the weighted portfolio and align with SPY later."""
    cols = {}
    for h in port.holdings:
        s = prices.get(h.profile.ticker)
        if s is not None:
            cols[h.profile.ticker] = s.pct_change()
    rets = pd.DataFrame(cols).dropna(how="all")
    weights = {h.profile.ticker: h.weight for h in port.holdings if h.profile.ticker in rets.columns}
    # Renormalize across names we actually have returns for (cash earns ~0).
    wsum = sum(weights.values())
    port_ret = sum(rets[t].fillna(0) * w for t, w in weights.items())
    # Keep cash drag: do NOT renormalize to 1; cash portion simply returns 0.
    return pd.DataFrame({"port": port_ret}).dropna()


def _max_drawdown(daily: pd.Series) -> float:
    curve = (1 + daily).cumprod()
    peak = curve.cummax()
    return float(((curve / peak) - 1).min() * 100)


def _sharpe(daily: pd.Series, rf_annual=0.043) -> float:
    ex = daily - rf_annual / 252
    sd = ex.std()
    return float((ex.mean() / sd) * np.sqrt(252)) if sd > 0 else 0.0


def stress_test(port: Portfolio, prices: Dict[str, pd.Series], market: pd.Series) -> StressReport:
    pr = _portfolio_returns(port, prices)
    mkt = market.pct_change().rename("spy")
    df = pd.concat([pr["port"].rename("port"), mkt], axis=1).dropna()

    port_r, spy_r = df["port"], df["spy"]

    # ── Daily up/down capture ────────────────────────────────────────────────
    down = spy_r < 0
    up = spy_r > 0
    dc = (port_r[down].mean() / spy_r[down].mean()) if down.any() and spy_r[down].mean() != 0 else float("nan")
    uc = (port_r[up].mean() / spy_r[up].mean()) if up.any() and spy_r[up].mean() != 0 else float("nan")
    capture_ratio = (uc / dc) if (dc and dc == dc and dc != 0) else float("nan")

    # ── Win rate in down MONTHS ──────────────────────────────────────────────
    monthly = df.resample("ME").apply(lambda x: (1 + x).prod() - 1)
    down_m = monthly[monthly["spy"] < 0]
    win_rate = float((down_m["port"] > down_m["spy"]).mean() * 100) if len(down_m) else float("nan")

    # ── Risk/return summary ──────────────────────────────────────────────────
    ann = lambda r: float(((1 + r).prod() ** (252 / len(r)) - 1) * 100)
    vol = lambda r: float(r.std() * np.sqrt(252) * 100)

    # ── Named stress windows ─────────────────────────────────────────────────
    windows = {}
    for label, (start, end) in STRESS_WINDOWS.items():
        seg = df.loc[start:end]
        if len(seg) >= 5:
            windows[label] = {
                "port": float(((1 + seg["port"]).prod() - 1) * 100),
                "spy":  float(((1 + seg["spy"]).prod() - 1) * 100),
            }

    return StressReport(
        downside_capture=round(dc, 3) if dc == dc else float("nan"),
        upside_capture=round(uc, 3) if uc == uc else float("nan"),
        capture_ratio=round(capture_ratio, 3) if capture_ratio == capture_ratio else float("nan"),
        win_rate_down_months=round(win_rate, 1) if win_rate == win_rate else float("nan"),
        port_max_drawdown=round(_max_drawdown(port_r), 1),
        spy_max_drawdown=round(_max_drawdown(spy_r), 1),
        port_ann_return=round(ann(port_r), 1),
        spy_ann_return=round(ann(spy_r), 1),
        port_ann_vol=round(vol(port_r), 1),
        spy_ann_vol=round(vol(spy_r), 1),
        port_sharpe=round(_sharpe(port_r), 2),
        spy_sharpe=round(_sharpe(spy_r), 2),
        stress_windows=windows,
    )
