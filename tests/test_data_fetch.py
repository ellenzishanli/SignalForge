"""
Regression tests for the trailing-NaN-close bug.

yfinance often returns today's un-settled bar as a row with a NaN Close. Taking
closes.iloc[-1] then made price (and every return / analyst-upside derived from
it) NaN, while .info-sourced fields (PE, revenue growth) still worked — exactly
the "$nan price but valid Fwd PE" pattern seen in the leaderboard. The fetchers
now drop NaN-close bars; these tests lock that in.
"""
import sys, os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def _frame_with_trailing_nan(n=300):
    idx = pd.bdate_range("2025-01-01", periods=n)
    close = np.linspace(100.0, 120.0, n)
    close[-1] = np.nan                      # today's un-settled bar
    return pd.DataFrame(
        {"Open": close, "High": close, "Low": close, "Close": close,
         "Volume": np.full(n, 1e6)},
        index=idx,
    )


class _FakeTicker:
    def __init__(self, *_a, **_k):
        pass

    def history(self, period=None, **_k):
        return _frame_with_trailing_nan()

    @property
    def info(self):
        return {"forwardPE": 20.0, "revenueGrowth": 0.30, "trailingPE": 25.0,
                "targetMeanPrice": 130.0, "shortName": "Test Co", "marketCap": 5e10}


def test_sector_fetch_handles_trailing_nan(monkeypatch):
    import stocks.sector_scan as ss
    monkeypatch.setattr(ss.yf, "Ticker", _FakeTicker)
    sd = ss.fetch_sector_stock("TEST", "AI")
    assert sd is not None
    assert sd.current_price == sd.current_price and sd.current_price > 0   # not NaN
    assert sd.return_6m == sd.return_6m                                    # not NaN
    assert sd.upside_to_target is not None


def test_screener_fetch_handles_trailing_nan(monkeypatch):
    import stocks.screener as sc
    monkeypatch.setattr(sc.yf, "Ticker", _FakeTicker)
    sd = sc.fetch_stock_data("TEST")
    assert sd is not None
    assert sd.current_price == sd.current_price and sd.current_price > 0
    assert sd.return_1y == sd.return_1y


def test_all_nan_frame_is_dropped(monkeypatch):
    """A fully NaN-close frame (e.g. hard rate-limit) should yield None, not a
    NaN-priced row — better to omit the name than show garbage."""
    import stocks.sector_scan as ss

    class _AllNaN(_FakeTicker):
        def history(self, period=None, **_k):
            df = _frame_with_trailing_nan()
            df["Close"] = np.nan
            return df

    monkeypatch.setattr(ss.yf, "Ticker", _AllNaN)
    assert ss.fetch_sector_stock("TEST", "AI") is None
