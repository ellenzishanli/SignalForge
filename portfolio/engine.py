"""
Orchestrator: universe → factor model → defensive construction → stress test.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.universe import PORTFOLIO_UNIVERSE
from portfolio.data import fetch_universe_prices
from portfolio.factor_model import compute_factor_profile, FactorProfile
from portfolio.factors import build_factor_returns, factor_proxy_tickers
from portfolio.construction import construct_defensive_portfolio, Portfolio
from portfolio.risk_parity import build_risk_parity_portfolio
from portfolio.max_sharpe import build_max_sharpe_portfolio
from portfolio.stress import stress_test, StressReport


@dataclass
class PortfolioResult:
    profiles: List[FactorProfile]
    portfolio: Portfolio
    stress: StressReport
    # Bridgewater-style Equal-Risk-Contribution book + its stress test, computed
    # over the same universe for a side-by-side comparison. Optional so older
    # callers and tests keep working.
    rp_portfolio: Optional[Portfolio] = None
    rp_stress: Optional[StressReport] = None
    # Return-seeking maximum-Sharpe (tangency) book + its stress test.
    ms_portfolio: Optional[Portfolio] = None
    ms_stress: Optional[StressReport] = None


def _sleeve_lookup(universe: Dict) -> Dict[str, tuple]:
    """ticker → (sleeve, name)."""
    out = {}
    for sleeve, names in universe.items():
        for ticker, name in names:
            out[ticker] = (sleeve, name)
    return out


def run_portfolio_engine(
    universe: Dict = None,
    period: str = "5y",
    target_beta: float = 0.60,
    include_risk_parity: bool = True,
    include_max_sharpe: bool = True,
    progress=None,
) -> PortfolioResult:
    universe = universe or PORTFOLIO_UNIVERSE
    meta = _sleeve_lookup(universe)
    # Fetch the universe plus the ETF proxies needed to build Fama-French factors.
    fetch_list = list(dict.fromkeys(list(meta.keys()) + factor_proxy_tickers()))

    market, prices = fetch_universe_prices(fetch_list, period=period, progress=progress)

    # Build the multi-factor return matrix (SPY market + size/value/mom/quality).
    factors = build_factor_returns({**prices, "SPY": market})

    profiles: List[FactorProfile] = []
    for ticker, closes in prices.items():
        if ticker not in meta:
            continue  # factor-proxy ETF that isn't part of the portfolio universe
        sleeve, name = meta.get(ticker, ("alpha", ticker))
        prof = compute_factor_profile(ticker, name, sleeve, closes, market, factors=factors)
        if prof is not None:
            profiles.append(prof)

    portfolio = construct_defensive_portfolio(profiles, target_beta=target_beta)
    stress = stress_test(portfolio, prices, market)

    rp_portfolio = rp_stress = None
    if include_risk_parity:
        rp_portfolio = build_risk_parity_portfolio(profiles, prices)
        rp_stress = stress_test(rp_portfolio, prices, market)

    ms_portfolio = ms_stress = None
    if include_max_sharpe:
        ms_portfolio = build_max_sharpe_portfolio(profiles, prices)
        ms_stress = stress_test(ms_portfolio, prices, market)

    return PortfolioResult(
        profiles=profiles, portfolio=portfolio, stress=stress,
        rp_portfolio=rp_portfolio, rp_stress=rp_stress,
        ms_portfolio=ms_portfolio, ms_stress=ms_stress,
    )
