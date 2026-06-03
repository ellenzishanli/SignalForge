"""
Defensive portfolio construction — AQR Total Portfolio Approach, applied.

Principle (AQR 2026): rank investments by APPRAISAL RATIO (alpha / residual vol)
and weight them proportionally — that maximizes the portfolio's risk-adjusted
improvement. We extend it with two defensive levers so the result loses less in
a selloff:

  1. Low-beta tilt (betting-against-beta): among two names with equal appraisal
     ratio, prefer the lower-beta one. Weight ∝ appraisal_ratio / beta^tilt.
  2. Beta target: after weighting the risky names, hold enough of the convexity
     sleeve (trend / anti-beta / gold / bonds) — and cash if needed — to pull the
     whole-portfolio beta down to the target (default 0.60, i.e. ~60% of the
     market's drawdown participation).

The output is a fully-specified weight per holding plus the portfolio's expected
beta, alpha, and a back-of-envelope "down-market capture".
"""
from dataclasses import dataclass, field
from typing import List, Dict
import numpy as np

from portfolio.factor_model import FactorProfile


@dataclass
class Holding:
    profile: FactorProfile
    weight: float              # final portfolio weight (fraction, 0–1)


@dataclass
class Portfolio:
    holdings: List[Holding]
    cash_weight: float
    target_beta: float
    port_beta: float           # weighted Dimson beta of the book
    port_downside_beta: float
    port_upside_beta: float
    port_alpha_annual: float   # weighted Jensen alpha, % per year
    port_appraisal: float      # weighted appraisal ratio
    sleeve_weights: Dict[str, float] = field(default_factory=dict)


def construct_defensive_portfolio(
    profiles: List[FactorProfile],
    target_beta: float = 0.60,
    low_beta_tilt: float = 1.0,
    max_weight: float = 0.12,
    min_appraisal: float = 0.0,
) -> Portfolio:
    """
    Build the portfolio. ``low_beta_tilt`` controls how hard we lean toward low
    beta (0 = pure appraisal-ratio weighting; 1 = divide weight by beta).
    """
    # ── 1. Risk sleeve (alpha + defensive): weight ∝ appraisal / beta^tilt ───
    risk_names = [p for p in profiles if p.sleeve in ("alpha", "defensive")]
    convex_names = [p for p in profiles if p.sleeve == "convexity"]

    scored = []
    for p in risk_names:
        ar = max(p.appraisal_ratio - min_appraisal, 0.0)
        if ar <= 0:
            continue
        beta_floor = max(p.beta, 0.15)  # avoid divide-by-tiny for near-zero beta
        raw = ar / (beta_floor ** low_beta_tilt)
        scored.append((p, raw))

    # Fallback: if nothing has positive alpha, hold only convexity + cash.
    risk_weights: Dict[str, float] = {}
    if scored:
        total = sum(w for _, w in scored)
        for p, w in scored:
            risk_weights[p.ticker] = w / total
        risk_weights = _cap_and_renorm(risk_weights, max_weight)

    # Provisional book = risk sleeve scaled so its own beta meets a stretch target,
    # then top up with the convexity sleeve to push beta down to target.
    risk_profiles = {p.ticker: p for p in risk_names}
    risk_beta = sum(risk_weights.get(t, 0) * risk_profiles[t].beta_lagged
                    for t in risk_weights) if risk_weights else 0.0

    # ── 2. Solve the sleeve split to hit the target beta ─────────────────────
    # Convexity sleeve gets equal weight internally; its blended beta is usually
    # negative or near zero, so adding it lowers the book beta.
    convex_beta = (np.mean([p.beta_lagged for p in convex_names])
                   if convex_names else 0.0)

    # We want: w_risk * risk_beta + w_convex * convex_beta = target_beta,
    # with w_risk + w_convex + cash = 1, cash >= 0. Prefer to stay fully invested
    # (cash=0) unless even 100% convexity can't get us low enough.
    w_risk, w_convex, cash = _solve_sleeves(risk_beta, convex_beta, target_beta)

    holdings: List[Holding] = []
    for t, w in risk_weights.items():
        holdings.append(Holding(risk_profiles[t], round(w * w_risk, 4)))
    if convex_names and w_convex > 0:
        per = w_convex / len(convex_names)
        for p in convex_names:
            holdings.append(Holding(p, round(per, 4)))

    holdings = [h for h in holdings if h.weight > 0.0005]
    holdings.sort(key=lambda h: h.weight, reverse=True)

    # ── 3. Portfolio-level analytics ─────────────────────────────────────────
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
        holdings=holdings, cash_weight=round(cash, 4), target_beta=target_beta,
        port_beta=round(port_beta, 3), port_downside_beta=round(port_dbeta, 3),
        port_upside_beta=round(port_ubeta, 3), port_alpha_annual=round(port_alpha, 2),
        port_appraisal=round(port_appr, 3),
        sleeve_weights={k: round(v, 4) for k, v in sleeve_w.items()},
    )


def _solve_sleeves(risk_beta, convex_beta, target_beta):
    """Find (w_risk, w_convex, cash) so blended beta == target, staying invested."""
    if risk_beta <= 0:
        return 0.0, 1.0, 0.0
    # Try fully invested: w_risk + w_convex = 1.
    # w_risk*risk_beta + (1-w_risk)*convex_beta = target  →  solve for w_risk.
    denom = (risk_beta - convex_beta)
    if abs(denom) > 1e-6:
        w_risk = (target_beta - convex_beta) / denom
    else:
        w_risk = target_beta / risk_beta
    w_risk = float(np.clip(w_risk, 0.0, 1.0))
    w_convex = 1.0 - w_risk
    # If even all-convexity leaves beta above target, hold cash to finish the job.
    blended = w_risk * risk_beta + w_convex * convex_beta
    cash = 0.0
    if blended > target_beta and convex_beta >= 0:
        scale = target_beta / blended if blended > 0 else 1.0
        w_risk *= scale
        w_convex *= scale
        cash = 1.0 - w_risk - w_convex
    return w_risk, w_convex, max(0.0, cash)


def _cap_and_renorm(weights: Dict[str, float], cap: float) -> Dict[str, float]:
    """Cap any single name at ``cap`` and renormalize, iterating until stable."""
    w = dict(weights)
    for _ in range(10):
        over = {k: v for k, v in w.items() if v > cap}
        if not over:
            break
        excess = sum(v - cap for v in over.values())
        for k in over:
            w[k] = cap
        under = {k: v for k, v in w.items() if v < cap}
        pool = sum(under.values())
        if pool <= 0:
            break
        for k in under:
            w[k] += excess * (w[k] / pool)
    total = sum(w.values())
    return {k: v / total for k, v in w.items()} if total else w


def _nz(x: float) -> float:
    return 0.0 if (x != x) else x  # NaN → 0
