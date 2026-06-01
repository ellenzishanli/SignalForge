import pytest
import numpy as np
import pandas as pd


@pytest.fixture
def trending_prices():
    """Upward trending price series, 252 days."""
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.015, 252)
    return pd.Series(100 * np.exp(np.cumsum(returns)))


@pytest.fixture
def flat_prices():
    np.random.seed(7)
    returns = np.random.normal(0.0, 0.01, 252)
    return pd.Series(100 * np.exp(np.cumsum(returns)))


@pytest.fixture
def ohlcv_df(trending_prices):
    return pd.DataFrame({
        "Close":  trending_prices,
        "High":   trending_prices * 1.005,
        "Low":    trending_prices * 0.995,
        "Volume": np.random.uniform(1e6, 1e7, len(trending_prices)),
    })
