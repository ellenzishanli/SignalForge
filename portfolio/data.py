"""
Price-history fetcher for the portfolio engine.

Pulls a multi-year daily close series for every name in the universe plus the
market benchmark (SPY), in parallel. A longer window than the rest of SignalForge
(default 5y) is needed so the factor regressions and stress tests have enough
up- and down-market days — including the 2022 bear market.
"""
from typing import Dict, List, Tuple, Optional
import pandas as pd
import yfinance as yf

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from stocks.parallel import parallel_fetch

MARKET_TICKER = "SPY"


def _fetch_closes(ticker: str, period: str) -> Optional[Tuple[str, pd.Series]]:
    try:
        hist = yf.Ticker(ticker).history(period=period)
        if hist.empty or len(hist) < 120:
            return None
        closes = hist["Close"].copy()
        closes.index = closes.index.tz_localize(None)  # normalize for clean alignment
        return (ticker, closes)
    except Exception:
        return None


def fetch_universe_prices(
    tickers: List[str], period: str = "5y", progress=None
) -> Tuple[pd.Series, Dict[str, pd.Series]]:
    """
    Returns (market_closes, {ticker: closes}) for all names that fetched cleanly.
    SPY is always included as the benchmark.
    """
    want = list(dict.fromkeys([MARKET_TICKER] + tickers))  # de-dup, keep order
    results = parallel_fetch(
        want, lambda t: _fetch_closes(t, period), progress=progress
    )
    by_ticker = {t: s for (t, s) in results}
    market = by_ticker.pop(MARKET_TICKER, None)
    if market is None:
        raise RuntimeError("Could not fetch SPY benchmark — cannot run factor model.")
    return market, by_ticker
