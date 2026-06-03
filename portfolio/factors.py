"""
Fama-French style multi-factor returns, built from liquid ETF proxies.

The single-SPY CAPM in factor_model.py explains very little of a high-beta growth
name's variance (PLTR's R² ≈ 0.02) — so its "alpha" is mostly unexplained residual,
not skill. A multi-factor model strips out the *known* return drivers (size, value,
momentum, quality) first; whatever is left is a far more honest alpha.

Kenneth French publishes the canonical factor series, but to stay offline and
dependency-free we reconstruct close proxies from ETFs the engine can already
fetch via yfinance:

  MKT  market excess     = SPY − risk-free
  SMB  size (small−big)  = IWM − SPY
  HML  value (val−grow)  = VTV − VUG
  MOM  momentum          = MTUM − SPY
  QMJ  quality           = QUAL − SPY    (Quality Minus Junk proxy)

These are long-short *spread* returns, exactly the form a factor regression wants.
"""
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from portfolio.factor_model import TRADING_DAYS, DEFAULT_RF_ANNUAL

# Long leg / short leg for each factor spread. MKT is handled as an excess return.
FACTOR_PROXIES = {
    "smb": ("IWM", "SPY"),   # small minus big
    "hml": ("VTV", "VUG"),   # value minus growth
    "mom": ("MTUM", "SPY"),  # momentum minus market
    "qmj": ("QUAL", "SPY"),  # quality minus market
}
FACTOR_COLUMNS = ["mkt", "smb", "hml", "mom", "qmj"]


def factor_proxy_tickers() -> List[str]:
    """The ETF tickers needed to build the factor series (de-duplicated)."""
    want = ["SPY"]
    for long_t, short_t in FACTOR_PROXIES.values():
        want += [long_t, short_t]
    return list(dict.fromkeys(want))


def build_factor_returns(
    prices: Dict[str, pd.Series], rf_annual: float = DEFAULT_RF_ANNUAL
) -> Optional[pd.DataFrame]:
    """
    Build a daily factor-return frame (columns = FACTOR_COLUMNS) from a dict of
    ETF close-price series. Returns None if the core proxies are missing.
    """
    def rets(ticker: str) -> Optional[pd.Series]:
        s = prices.get(ticker)
        return s.pct_change() if s is not None else None

    spy = rets("SPY")
    if spy is None:
        return None

    rf_daily = rf_annual / TRADING_DAYS
    cols = {"mkt": spy - rf_daily}
    for name, (long_t, short_t) in FACTOR_PROXIES.items():
        rl, rs = rets(long_t), rets(short_t)
        if rl is None or rs is None:
            continue
        cols[name] = rl - rs

    df = pd.DataFrame(cols).dropna()
    if df.empty or "mkt" not in df.columns:
        return None
    return df
