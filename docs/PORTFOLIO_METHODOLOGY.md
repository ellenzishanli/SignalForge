# Defensive Alpha — Methodology & Concepts

> The portfolio engine behind `python3 main.py --mode portfolio`.
> Goal: **keep most of the upside, lose far less when the market falls.**
> Grounded in AQR's *Alternative Thinking 2026* research (Total Portfolio Approach,
> Capital Market Assumptions) and Cliff Asness's writing on diversification.

This doc is written to teach the concepts, not just document the code. If you read
it top to bottom you'll understand *why* the portfolio is built the way it is.

---

## 1. The core idea: separate beta from alpha

Every stock's return can be split into two parts:

```
stock return  =  beta × market return   +   alpha   +   noise
                 └─────────┬─────────┘       └──┬──┘
                  the market (free)         your real edge
```

- **Beta** is your sensitivity to the market. A beta of 2.0 means when the S&P 500
  (SPY) falls 1%, you tend to fall ~2%. You can buy beta for free with an index
  fund — *nobody should pay active fees for beta.*
- **Alpha** is what's left after removing beta. It's the genuine, unique return that
  isn't explained by just riding the market. **Only alpha improves a diversified
  portfolio** — because the beta part is return you already own everywhere else.

We estimate both with a simple regression (CAPM): regress the stock's daily
excess-of-cash returns on the market's. The slope is **beta**, the intercept is
**alpha** (annualized = *Jensen's alpha*).

> **Why you asked for "beta-adjusted alpha":** a raw return number flatters anything
> in a bull market — of course your 2-beta stock is up a lot, the market is up. The
> question that matters is: *after I strip out the free market ride, is there
> anything left?* That residual, risk-adjusted, is the number below.

---

## 2. The appraisal ratio — your beta-adjusted alpha score

Alpha alone isn't enough: 5% alpha earned smoothly is far better than 5% alpha that
swings ±40% along the way. So we divide alpha by the volatility of the *unique*
(idiosyncratic) return:

```
appraisal ratio  =  alpha  ÷  idiosyncratic volatility
```

This is straight out of AQR's **Total Portfolio Approach** paper. Their prescription:
> *"The portfolio weight in a new investment should be proportional to its appraisal
> ratio."*

It's the information ratio applied to the market-residual. A name with a **high
appraisal ratio** delivers a lot of unique return per unit of unique risk — exactly
what you want to size up. This engine ranks every name by it and weights accordingly.

In AQR's Exhibit 1, hedge funds and trend-following have much higher appraisal ratios
than private equity or high-yield bonds — *not* because they have higher returns, but
because so little of their return overlaps with stocks/bonds you already own.

---

## 3. Dimson beta — catching "hidden" market risk

Some assets react to the market with a **delay** — their reported price digests a
market move over several days. Plain beta then *understates* their true market risk.
Asness's classic finding ("Do Hedge Funds Hedge?") is that adding *lagged* market
returns to the regression reveals the real exposure.

We compute a **Dimson beta** = contemporaneous beta + 1-day lagged beta. We use this
"true beta" for portfolio construction, so we don't get fooled into thinking
something is more defensive than it really is. (This is also the antidote to
"volatility laundering" — the way illiquid/smoothed assets pretend to be low-risk.)

---

## 4. Convexity — the asymmetry we actually want

The holy grail (AQR's words): an investment that **outperforms in an equity bear
market without dragging on long-term returns.** We measure the asymmetry directly:

```
downside beta  =  beta measured ONLY on days the market fell
upside beta    =  beta measured ONLY on days the market rose
convexity      =  upside beta − downside beta     (positive is good)
```

A **positive convexity** name participates on the way up but resists on the way
down. That's the profile that lets a portfolio compound through cycles instead of
giving it all back in the next crash.

---

## 5. Construction — how the book is built

Three sleeves, each doing a job:

| Sleeve | Job | Examples |
|--------|-----|----------|
| 🟢 **Alpha** | Return engine — high beta-adjusted alpha | NVDA, AVGO, CEG, GEV, META |
| 🔵 **Defensive** | Low-beta equity ballast — falls less | BRK-B, COST, XLU, XLP, XLV, SCHD |
| 🟣 **Convexity** | True crisis diversifiers | DBMF/KMLM (trend), BTAL (anti-beta), GLD, TLT |

**Steps:**
1. Compute every name's factor profile (beta, Dimson beta, alpha, appraisal, convexity).
2. **Weight the risk sleeve ∝ appraisal ratio**, then apply a **low-beta tilt**
   (divide by beta) — this is the *betting-against-beta* factor: among equal-alpha
   names, prefer the lower-beta one. Cap any single name (default 12%).
3. **Add the convexity sleeve** and, if needed, cash, in exactly the proportion that
   pulls the *whole-portfolio Dimson beta* down to the target (default **0.60**).

Why those convexity ETFs? AQR's research is blunt about it: over 26 years,
**trend-following** (managed futures) earned a positive ~5.4%/yr **and** cushioned
drawdowns — the single best crisis diversifier. By contrast, **buying put options**
works as a hedge but bleeds ~−3%/yr, so it lowers long-run returns. DBMF/KMLM give
us trend exposure; **BTAL** is literally long low-beta / short high-beta.

---

## 5b. A second lens — Risk Parity (Bridgewater "All Weather")

The Defensive Alpha book above sizes positions by *return quality* (appraisal
ratio). Risk Parity asks a different question entirely: **forget expected return —
what if every holding contributed the same amount of risk?**

The motivation is Bridgewater's classic observation about 60/40. It *looks*
balanced by dollars, but stocks are ~3–4× as volatile as bonds, so ~90% of the
portfolio's day-to-day P&L is driven by equities. The bonds are along for the
ride. **Equalizing risk contribution** instead of dollars fixes that.

Formally, with covariance matrix Σ and weights w:

- Portfolio vol: σ(w) = √(wᵀΣw)
- Asset *i*'s risk contribution: RCᵢ = wᵢ · (Σw)ᵢ / σ(w), and Σᵢ RCᵢ = σ(w)
- **Equal Risk Contribution (ERC):** choose w so RCᵢ = σ(w)/n for every *i*.

We solve it with **cyclical coordinate descent** (Griveau-Billion, Richard &
Roncalli 2013): sweep through the assets, and for each one solve the 1-D quadratic
that sets its risk contribution to target while holding the others fixed. It is
long-only by construction and converges in a few sweeps. The effect: low-vol
ballast (bonds, gold, defensives) is scaled **up**, high-vol growth scaled
**down**, until the risk budget is even.

The terminal builds *both* books on the **same universe** and prints them
head-to-head — AQR's return-quality sizing vs Bridgewater's risk-balanced sizing —
on annual return, vol, Sharpe, max drawdown, downside capture and beta. Neither is
strictly "better": Defensive Alpha leans on a return view, Risk Parity makes no
return forecast at all and is more robust when those forecasts are wrong.

---

## 6. The payoff — how we measure "win when the market is down"

The stress test builds the portfolio's daily return series and asks:

| Metric | What it means | Good |
|--------|---------------|------|
| **Downside capture** | Your share of SPY's *down* days | < 0.7 |
| **Upside capture** | Your share of SPY's *up* days | high |
| **Capture ratio** | upside ÷ downside | > 1.0 |
| **Win rate, down months** | % of red-SPY months you still beat SPY | > 60% |
| **Max drawdown** | Worst peak-to-trough vs SPY | shallower than SPY |
| **Stress windows** | Cumulative return through 2022 bear, 2025 tariff shock | beat SPY |

A downside capture of 0.50 with upside capture of 0.65 means: *you take half the
market's pain but keep two-thirds of its gains* — favorable convexity, which over
time produces higher compound returns with smaller drawdowns.

---

## 7. Honest limitations

- **Backward-looking.** Betas, alphas and correlations are estimated on the trailing
  5 years. They drift. A name's past alpha is not a promise of future alpha.
- **No transaction costs / rebalancing model.** Weights are a point-in-time target.
- **ETF proxies for convexity** (DBMF, BTAL) have shorter histories and their own
  manager/strategy risk.
- **Diversification is not a hedge.** As Asness says, it won't save you in *every*
  drawdown — but over longer periods it really helps.
- This is **research tooling, not investment advice.**

---

## References

- AQR, *Alternative Thinking 2026 — Total Portfolio Approach* (appraisal ratio,
  factor diversification, search for convexity, trend vs puts).
- AQR, *Alternative Thinking 2026 — Capital Market Assumptions* (compressed risk
  premia; 60/40 expected real return ~3.4%).
- Asness et al., *Do Hedge Funds Hedge?* (lagged/Dimson betas, understated exposure).
- Asness, *Journal of Private Markets Investing*, Spring 2026 (volatility laundering;
  trend-following as the best "doom scenario" diversifier).
- Maillard, Roncalli & Teiletche, *The Properties of Equally Weighted Risk
  Contribution Portfolios* (2010) — the risk parity / ERC framework.
- Griveau-Billion, Richard & Roncalli, *A Fast Algorithm for Computing High-
  Dimensional Risk Parity Portfolios* (2013) — the cyclical coordinate descent solver.
- Bridgewater Associates, *The All Weather Story* — risk-balanced asset allocation.
- Asness, Frazzini & Pedersen, *Quality Minus Junk* (2019) — the QMJ quality factor
  (profitability, growth, safety) used in the stock-level fundamental score.
