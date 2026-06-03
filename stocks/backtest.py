"""
Walk-Forward Backtester + Factor Weight Optimizer
==================================================
Runs a proper walk-forward backtest on ~20 tickers:
  - Monthly evaluation points over the last 10 months
  - Only uses data available at each evaluation point (no look-ahead)
  - Measures 30-day forward returns vs SPY
  - Reports win rate, mean return, IC, Sharpe of BUY+ strategy vs SPY
  - OLS regression to derive empirically optimal factor weights
  - Rich table rendering for a professional quant backtest report
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field

BACKTEST_TICKERS = [
    "NVDA", "MSFT", "GOOGL", "AMZN", "META",   # mega-cap tech
    "PLTR", "NET", "SNOW", "CRWD",              # growth SaaS
    "LMT", "RTX",                               # defense
    "ENPH", "FSLR",                             # clean energy
    "RXRX", "CRSP",                             # biotech
    "COIN", "HOOD",                             # fintech/crypto
    "ASTS", "RKLB",                             # speculative/space
    "JPM", "V",                                 # financials
]

# Price-only composite weights (no fundamental — no historical data available)
PRICE_WEIGHTS = {"tech": 0.25, "stat": 0.35, "ml": 0.25, "risk": 0.15}

# Assumed round-trip transaction cost per monthly rebalance (commission + spread +
# slippage), in % of notional. A monthly-rebalanced book pays this every period,
# so net performance is what actually matters — gross Sharpe flatters the model.
TXN_COST_ROUNDTRIP_PCT = 0.20

# Signal thresholds (match quant.py convention)
def _score_to_signal(score: float) -> str:
    if   score >= 72: return "STRONG_BUY"
    elif score >= 58: return "BUY"
    elif score >= 42: return "HOLD"
    elif score >= 28: return "SELL"
    else:             return "STRONG_SELL"


@dataclass
class SignalRecord:
    ticker: str
    eval_date: str
    tech_score: float
    stat_score: float
    ml_score: float
    risk_score: float
    composite_score: float
    signal: str
    forward_30d_return: float   # % return over next 30 calendar days
    spy_30d_return: float       # SPY return over same window
    excess_return: float        # forward_30d_return - spy_30d_return


def _compute_price_composite(closes: pd.Series, hist_df: pd.DataFrame) -> dict:
    """Compute price-only factor scores. Returns dict with tech/stat/ml/risk scores."""
    from stocks.technical import compute_technical_score
    from stocks.risk_metrics import compute_ml_trend, compute_risk_metrics
    from stocks.quant import _compute_statistical

    try:
        tech = compute_technical_score(closes, hist_df)
        tech_score = float(tech.composite_score)
    except Exception:
        tech_score = 50.0

    try:
        stat = _compute_statistical(closes)
        stat_score = float(stat.composite_score)
    except Exception:
        stat_score = 50.0

    try:
        ml = compute_ml_trend(closes)
        ml_score = float(ml.ml_score)
    except Exception:
        ml_score = 50.0

    try:
        risk = compute_risk_metrics(closes)
        risk_score = float(risk.risk_score)
    except Exception:
        risk_score = 50.0

    composite = (
        tech_score * PRICE_WEIGHTS["tech"] +
        stat_score * PRICE_WEIGHTS["stat"] +
        ml_score   * PRICE_WEIGHTS["ml"] +
        risk_score * PRICE_WEIGHTS["risk"]
    )
    composite = round(composite, 1)

    return {
        "tech": tech_score,
        "stat": stat_score,
        "ml": ml_score,
        "risk": risk_score,
        "composite": composite,
    }


def compute_period_ic(df_records, score_col="composite", ret_col="fwd_ret",
                      date_col="eval_date") -> dict:
    """
    Rank Information Coefficient, computed per rebalance period then aggregated —
    the right way to measure predictive power (a single pooled IC mixes regimes).

      mean_ic      — average cross-sectional rank corr(score, forward return)
      ic_std       — period-to-period volatility of the IC
      ic_ir        — IC information ratio = mean_ic / ic_std (consistency)
      t_stat       — mean_ic / (ic_std / sqrt(n)) — is the IC distinguishable from 0?
      pct_positive — % of periods with a positive IC

    Rule of thumb: a stable mean IC of 0.03–0.08 is a genuinely useful factor;
    near 0 (or t-stat < ~2) means little real predictive power.
    """
    ics = []
    for _, g in df_records.groupby(date_col):
        if len(g) < 5:
            continue
        sr = g[score_col].rank()
        rr = g[ret_col].rank()
        if sr.std(ddof=0) == 0 or rr.std(ddof=0) == 0:
            continue
        ic = float(np.corrcoef(sr, rr)[0, 1])
        if ic == ic:
            ics.append(ic)
    ics = np.array(ics)
    if len(ics) == 0:
        return {"mean_ic": float("nan"), "ic_std": float("nan"), "ic_ir": float("nan"),
                "t_stat": float("nan"), "pct_positive": float("nan"), "n_periods": 0}
    mean = float(ics.mean())
    std = float(ics.std(ddof=1)) if len(ics) > 1 else 0.0
    ir = mean / std if std > 0 else float("nan")
    t_stat = mean / (std / np.sqrt(len(ics))) if std > 0 else float("nan")
    return {
        "mean_ic": round(mean, 4), "ic_std": round(std, 4),
        "ic_ir": round(ir, 3) if ir == ir else float("nan"),
        "t_stat": round(t_stat, 2) if t_stat == t_stat else float("nan"),
        "pct_positive": round(float((ics > 0).mean() * 100), 1),
        "n_periods": int(len(ics)),
    }


def compute_quantile_performance(df_records, n_buckets=5, score_col="composite",
                                 ret_col="fwd_ret", date_col="eval_date") -> dict:
    """
    Sort names into ``n_buckets`` by score each period and track each bucket's mean
    forward return. A working model is monotonic (higher bucket → higher return)
    with a positive top-minus-bottom (long-short) spread.
    """
    bucket_rets = {i: [] for i in range(n_buckets)}
    n_periods = 0
    for _, g in df_records.groupby(date_col):
        if len(g) < n_buckets:
            continue
        ranks = g[score_col].rank(method="first")
        try:
            buckets = pd.qcut(ranks, n_buckets, labels=False)
        except ValueError:
            continue
        n_periods += 1
        for b, gg in g.groupby(buckets):
            bucket_rets[int(b)].append(float(gg[ret_col].mean()))
    means = [round(float(np.mean(bucket_rets[i])), 2) if bucket_rets[i] else float("nan")
             for i in range(n_buckets)]
    lo, hi = means[0], means[-1]
    spread = round(hi - lo, 2) if lo == lo and hi == hi else float("nan")
    valid = [m for m in means if m == m]
    monotonic = (len(valid) == len(means)
                 and all(means[i] <= means[i + 1] + 1e-9 for i in range(len(means) - 1)))
    return {"bucket_means": means, "long_short_spread": spread,
            "monotonic": bool(monotonic), "n_periods": n_periods}


def run_backtest_and_display(console=None):
    """
    Walk-forward backtest entry point. Downloads price data, runs monthly
    signal generation with strict look-ahead prevention, computes forward
    returns, and renders a professional quant backtest report.
    """
    import yfinance as yf
    from rich.console import Console
    from rich.table import Table
    from rich.rule import Rule
    from rich.panel import Panel
    from rich.text import Text

    if console is None:
        console = Console(width=200)

    console.print(Rule("[bold cyan]Walk-Forward Backtest + Factor Weight Optimization[/bold cyan]"))
    console.print(f"[dim]Tickers: {len(BACKTEST_TICKERS)} | Lookback: 10 months | Forward window: 30 days[/dim]\n")

    # ── 1. Download price data ────────────────────────────────────────────────
    console.print("[bold]Downloading price data (18mo history)...[/bold]")

    price_cache: dict[str, pd.DataFrame] = {}
    failed = []
    for i, ticker in enumerate(BACKTEST_TICKERS):
        try:
            df = yf.Ticker(ticker).history(period="18mo")
            if df.empty or len(df) < 100:
                failed.append(ticker)
                continue
            # Normalize timezone-aware index
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            price_cache[ticker] = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        except Exception as e:
            failed.append(ticker)

    # Also download SPY for benchmark
    try:
        spy_df = yf.Ticker("SPY").history(period="18mo")
        if spy_df.index.tz is not None:
            spy_df.index = spy_df.index.tz_localize(None)
        spy_closes = spy_df["Close"]
    except Exception:
        spy_closes = None

    loaded = len(price_cache)
    console.print(f"  [green]✓[/green] {loaded} tickers loaded" +
                  (f" | [yellow]Failed: {failed}[/yellow]" if failed else "") + "\n")

    if loaded == 0:
        console.print("[red]No data loaded. Check network/yfinance.[/red]")
        return

    # ── 2. Build monthly evaluation schedule ─────────────────────────────────
    today = pd.Timestamp.today().normalize()
    eval_dates = []
    for m in range(10, 0, -1):
        # Roughly 30-day spacing, going back 10 months
        candidate = today - pd.DateOffset(days=30 * m)
        eval_dates.append(candidate)

    # ── 3. Walk-forward signal generation ────────────────────────────────────
    console.print("[bold]Running walk-forward signal generation...[/bold]")
    records: list[SignalRecord] = []

    for eval_dt in eval_dates:
        eval_str = eval_dt.strftime("%Y-%m-%d")

        for ticker, df in price_cache.items():
            # Slice to data available at eval_date (strict look-ahead prevention)
            avail = df[df.index <= eval_dt]
            if len(avail) < 60:
                continue

            closes = avail["Close"]
            hist_sub = avail[["Open", "High", "Low", "Close", "Volume"]]

            # Compute scores using only data up to eval_dt
            try:
                factors = _compute_price_composite(closes, hist_sub)
            except Exception:
                continue

            # Compute 30-day forward return (uses future data — only for labels)
            fwd_start = eval_dt
            fwd_end = eval_dt + pd.DateOffset(days=35)  # a few extra days for market closure
            fwd_window = df[(df.index > fwd_start) & (df.index <= fwd_end)]["Close"]

            if len(fwd_window) < 15:
                continue  # not enough future data

            fwd_return = round((float(fwd_window.iloc[-1]) / float(closes.iloc[-1]) - 1) * 100, 2)

            # SPY forward return for same window
            spy_fwd_ret = 0.0
            if spy_closes is not None:
                spy_fwd = spy_closes[(spy_closes.index > fwd_start) & (spy_closes.index <= fwd_end)]
                spy_prev = spy_closes[spy_closes.index <= fwd_start]
                if len(spy_fwd) >= 15 and len(spy_prev) >= 1:
                    spy_fwd_ret = round((float(spy_fwd.iloc[-1]) / float(spy_prev.iloc[-1]) - 1) * 100, 2)

            records.append(SignalRecord(
                ticker=ticker,
                eval_date=eval_str,
                tech_score=factors["tech"],
                stat_score=factors["stat"],
                ml_score=factors["ml"],
                risk_score=factors["risk"],
                composite_score=factors["composite"],
                signal=_score_to_signal(factors["composite"]),
                forward_30d_return=fwd_return,
                spy_30d_return=spy_fwd_ret,
                excess_return=round(fwd_return - spy_fwd_ret, 2),
            ))

    console.print(f"  [green]✓[/green] {len(records)} signal records generated\n")

    if len(records) < 10:
        console.print("[yellow]Not enough records for meaningful backtest.[/yellow]")
        return

    # ── 4. Analytics ─────────────────────────────────────────────────────────
    df_records = pd.DataFrame([
        {
            "ticker": r.ticker,
            "eval_date": r.eval_date,
            "tech": r.tech_score,
            "stat": r.stat_score,
            "ml": r.ml_score,
            "risk": r.risk_score,
            "composite": r.composite_score,
            "signal": r.signal,
            "fwd_ret": r.forward_30d_return,
            "spy_ret": r.spy_30d_return,
            "excess": r.excess_return,
        }
        for r in records
    ])

    SIGNAL_ORDER = ["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"]

    signal_stats = {}
    for sig in SIGNAL_ORDER:
        sub = df_records[df_records["signal"] == sig]
        if len(sub) == 0:
            signal_stats[sig] = {"count": 0, "win_rate": float("nan"),
                                 "mean_ret": float("nan"), "mean_excess": float("nan")}
            continue
        wins = (sub["fwd_ret"] > 0).sum()
        signal_stats[sig] = {
            "count": len(sub),
            "win_rate": round(wins / len(sub) * 100, 1),
            "mean_ret": round(sub["fwd_ret"].mean(), 2),
            "mean_excess": round(sub["excess"].mean(), 2),
        }

    # IC — information coefficient (Pearson corr of score vs forward return)
    scores_arr = df_records["composite"].values.astype(float)
    fwd_arr    = df_records["fwd_ret"].values.astype(float)
    ic = float(np.corrcoef(scores_arr, fwd_arr)[0, 1])
    ic = round(ic, 4)

    # Sharpe of BUY+ strategy vs SPY
    buy_plus = df_records[df_records["signal"].isin(["STRONG_BUY", "BUY"])]
    if len(buy_plus) >= 5:
        strategy_excess = buy_plus["excess"].values.astype(float)
        # Monthly periods → annualize with sqrt(12)
        ann_factor = np.sqrt(12)
        strategy_sharpe = round(
            float(strategy_excess.mean() / (strategy_excess.std() + 1e-9) * ann_factor), 2
        )
        strategy_mean_ret = round(float(buy_plus["fwd_ret"].mean()), 2)
        strategy_win_rate = round(float((buy_plus["fwd_ret"] > 0).mean() * 100), 1)
        # Net of transaction costs: subtract a round-trip cost from each period.
        net_excess = strategy_excess - TXN_COST_ROUNDTRIP_PCT
        strategy_sharpe_net = round(float(net_excess.mean() / (net_excess.std() + 1e-9) * ann_factor), 2)
        strategy_mean_ret_net = round(float(buy_plus["fwd_ret"].mean() - TXN_COST_ROUNDTRIP_PCT), 2)
    else:
        strategy_sharpe = float("nan")
        strategy_mean_ret = float("nan")
        strategy_win_rate = float("nan")
        strategy_sharpe_net = float("nan")
        strategy_mean_ret_net = float("nan")

    spy_monthly_avg = round(float(df_records["spy_ret"].mean()), 2)

    # ── 5. OLS Weight Optimization ───────────────────────────────────────────
    X = df_records[["tech", "stat", "ml", "risk"]].values.astype(float)
    y = df_records["fwd_ret"].values.astype(float)

    # OLS via numpy lstsq
    coeffs, residuals, rank, sv = np.linalg.lstsq(X, y, rcond=None)

    # Normalize to sum to 1 (treat negative weights as 0 before normalizing)
    raw_weights = coeffs.copy()
    clipped = np.clip(raw_weights, 0, None)
    weight_sum = clipped.sum()
    if weight_sum > 1e-9:
        optimal_weights = clipped / weight_sum
    else:
        optimal_weights = np.array([0.25, 0.35, 0.25, 0.15])  # fallback to hand-set

    opt_tech = round(float(optimal_weights[0]), 3)
    opt_stat = round(float(optimal_weights[1]), 3)
    opt_ml   = round(float(optimal_weights[2]), 3)
    opt_risk = round(float(optimal_weights[3]), 3)

    # ── 6. Render Rich Tables ─────────────────────────────────────────────────

    # Table 1: Signal performance by category
    t1 = Table(
        title="[bold]Signal Performance by Category (30-Day Forward Returns)[/bold]",
        show_header=True, header_style="bold magenta",
        border_style="bright_blue",
    )
    t1.add_column("Signal",        style="bold",  width=14)
    t1.add_column("Count",         justify="right", width=8)
    t1.add_column("Win Rate",      justify="right", width=10)
    t1.add_column("Mean Ret %",    justify="right", width=12)
    t1.add_column("vs SPY (α) %",  justify="right", width=13)

    SIG_COLORS = {
        "STRONG_BUY": "bright_green",
        "BUY": "green",
        "HOLD": "yellow",
        "SELL": "red",
        "STRONG_SELL": "bright_red",
    }

    for sig in SIGNAL_ORDER:
        s = signal_stats[sig]
        color = SIG_COLORS.get(sig, "white")
        if s["count"] == 0:
            t1.add_row(
                f"[{color}]{sig}[/{color}]",
                "0", "—", "—", "—"
            )
        else:
            wr_str  = f"{s['win_rate']:.1f}%"
            ret_str = f"{s['mean_ret']:+.2f}%"
            exc_str = f"{s['mean_excess']:+.2f}%"
            t1.add_row(
                f"[{color}]{sig}[/{color}]",
                str(s["count"]),
                f"[{color}]{wr_str}[/{color}]",
                f"[{color}]{ret_str}[/{color}]",
                f"[{color}]{exc_str}[/{color}]",
            )

    # Table 2: Strategy summary
    t2 = Table(
        title="[bold]BUY+ Strategy vs SPY Benchmark[/bold]",
        show_header=True, header_style="bold cyan",
        border_style="bright_blue",
    )
    t2.add_column("Metric",  width=30)
    t2.add_column("Value",   justify="right", width=16)
    t2.add_column("Notes",   width=40)

    ic_color = "green" if ic > 0.05 else ("yellow" if ic > 0 else "red")
    sharpe_color = "green" if (not np.isnan(strategy_sharpe) and strategy_sharpe > 0.5) else "yellow"

    t2.add_row("Total signal records",       str(len(records)),          "monthly × tickers")
    t2.add_row("Evaluation months",          "10",                       "walk-forward windows")
    t2.add_row("Tickers in universe",        str(loaded),                "~20 liquid names")
    t2.add_row("BUY+ win rate",
               f"[{sharpe_color}]{strategy_win_rate:.1f}%[/{sharpe_color}]" if not np.isnan(strategy_win_rate) else "N/A",
               "% months with positive return")
    t2.add_row("BUY+ mean monthly return",
               f"[green]{strategy_mean_ret:+.2f}%[/green]" if not np.isnan(strategy_mean_ret) else "N/A",
               "avg 30-day return for BUY/STRONG_BUY")
    t2.add_row("SPY mean monthly return",    f"{spy_monthly_avg:+.2f}%", "benchmark over same periods")
    t2.add_row("BUY+ Sharpe (annualized, gross)",
               f"[{sharpe_color}]{strategy_sharpe:.2f}[/{sharpe_color}]" if not np.isnan(strategy_sharpe) else "N/A",
               ">0.5 is reasonable, >1.0 is strong")
    t2.add_row("BUY+ mean return (net of costs)",
               f"[yellow]{strategy_mean_ret_net:+.2f}%[/yellow]" if not np.isnan(strategy_mean_ret_net) else "N/A",
               f"after {TXN_COST_ROUNDTRIP_PCT:.2f}% round-trip per rebalance")
    t2.add_row("BUY+ Sharpe (net of costs)",
               f"[{sharpe_color}]{strategy_sharpe_net:.2f}[/{sharpe_color}]" if not np.isnan(strategy_sharpe_net) else "N/A",
               "the number that actually matters")
    t2.add_row(
        "IC (Information Coefficient)",
        f"[{ic_color}]{ic:.4f}[/{ic_color}]",
        "[dim]IC>0.05 is meaningful in professional quant finance[/dim]",
    )

    # Table 3: Factor weight comparison
    t3 = Table(
        title="[bold]Factor Weight Comparison: Hand-Set vs OLS-Optimal[/bold]",
        show_header=True, header_style="bold yellow",
        border_style="bright_blue",
    )
    t3.add_column("Factor",       width=14)
    t3.add_column("Hand-Set",     justify="right", width=12)
    t3.add_column("OLS-Optimal",  justify="right", width=14)
    t3.add_column("Raw OLS coef", justify="right", width=14)
    t3.add_column("Δ",            justify="right", width=10)

    hand_weights = {
        "Technical":   PRICE_WEIGHTS["tech"],
        "Statistical": PRICE_WEIGHTS["stat"],
        "ML Trend":    PRICE_WEIGHTS["ml"],
        "Risk":        PRICE_WEIGHTS["risk"],
    }
    ols_weights_map = {
        "Technical":   opt_tech,
        "Statistical": opt_stat,
        "ML Trend":    opt_ml,
        "Risk":        opt_risk,
    }
    raw_map = {
        "Technical":   round(float(raw_weights[0]), 4),
        "Statistical": round(float(raw_weights[1]), 4),
        "ML Trend":    round(float(raw_weights[2]), 4),
        "Risk":        round(float(raw_weights[3]), 4),
    }

    for factor, hw in hand_weights.items():
        ow = ols_weights_map[factor]
        rw = raw_map[factor]
        delta = ow - hw
        d_color = "green" if abs(delta) < 0.05 else "yellow"
        t3.add_row(
            factor,
            f"{hw:.2%}",
            f"{ow:.2%}",
            f"{rw:+.4f}",
            f"[{d_color}]{delta:+.2%}[/{d_color}]",
        )

    # ── Table 4: Predictive-power validation (per-period rank IC + quantiles) ──
    ic_stats = compute_period_ic(df_records)
    q_stats = compute_quantile_performance(df_records, n_buckets=5)

    t4 = Table(
        title="[bold]Predictive Power — Rank IC & Score Quintiles (walk-forward)[/bold]",
        show_header=True, header_style="bold green", border_style="bright_blue",
    )
    t4.add_column("Metric", width=30)
    t4.add_column("Value", justify="right", width=16)
    t4.add_column("Read", width=46)

    mic = ic_stats["mean_ic"]
    mic_color = "green" if (mic == mic and mic > 0.03) else ("yellow" if (mic == mic and mic > 0) else "red")
    t4.add_row("Mean rank IC (per period)",
               f"[{mic_color}]{mic:.4f}[/{mic_color}]" if mic == mic else "N/A",
               "0.03–0.08 = genuinely useful; ~0 = no edge")
    t4.add_row("IC information ratio",
               f"{ic_stats['ic_ir']:.2f}" if ic_stats['ic_ir'] == ic_stats['ic_ir'] else "N/A",
               "mean IC ÷ its volatility (consistency)")
    t4.add_row("IC t-stat",
               f"{ic_stats['t_stat']:.2f}" if ic_stats['t_stat'] == ic_stats['t_stat'] else "N/A",
               "[dim]|t| > 2 → IC distinguishable from zero[/dim]")
    t4.add_row("% periods IC > 0",
               f"{ic_stats['pct_positive']:.0f}%" if ic_stats['pct_positive'] == ic_stats['pct_positive'] else "N/A",
               f"across {ic_stats['n_periods']} rebalance periods")
    bm = q_stats["bucket_means"]
    bm_str = " → ".join(f"{m:+.1f}" if m == m else "—" for m in bm)
    t4.add_row("Quintile mean fwd ret % (Q1→Q5)", bm_str, "monotone rising = score ranks names well")
    ls = q_stats["long_short_spread"]
    ls_color = "green" if (ls == ls and ls > 0) else "red"
    t4.add_row("Top-minus-bottom spread",
               f"[{ls_color}]{ls:+.2f}%[/{ls_color}]" if ls == ls else "N/A",
               f"Q5 − Q1; monotonic={q_stats['monotonic']}")

    # ── Render all tables ──
    console.print(t1)
    console.print()
    console.print(t2)
    console.print()
    console.print(t3)
    console.print()
    console.print(t4)
    console.print()

    # ── Interpretation panel ──
    ic_interp = (
        f"[green]IC={ic:.4f} — statistically meaningful (>0.05 threshold)[/green]"
        if ic > 0.05
        else f"[yellow]IC={ic:.4f} — below 0.05 threshold; model has weak predictive signal[/yellow]"
    )

    weight_note = ""
    big_diff = [(f, abs(ols_weights_map[f] - hand_weights[f])) for f in hand_weights if abs(ols_weights_map[f] - hand_weights[f]) > 0.08]
    if big_diff:
        top = max(big_diff, key=lambda x: x[1])
        weight_note = f"\n  [yellow]Largest weight divergence: {top[0]} (delta {top[1]:.1%}) — consider rebalancing.[/yellow]"

    summary = Panel(
        f"""[bold]Backtest Summary[/bold]

  Universe: {loaded} tickers across mega-cap tech, SaaS, defense, clean energy, biotech, fintech, space
  Evaluation: 10 monthly walk-forward points, 30-day forward return windows, strict no-look-ahead

  {ic_interp}

  Information Coefficient (IC) is the Pearson correlation between the model's composite score
  and the 30-day forward return. In professional quant finance, IC>0.05 is considered
  statistically meaningful; IC>0.10 is strong. Most institutional factor models target IC 0.03–0.08.

  OLS weight optimization: regressed raw factor scores against realized forward returns.
  Normalized positive coefficients give empirically-derived weights from this backtest period.{weight_note}

  [yellow]Caveats (read before trusting any number above):[/yellow]
  [dim]• Survivorship bias — the {loaded}-ticker universe is names still listed today; delisted/blown-up
    losers were never in the sample, so realized returns will be LOWER than shown.
  • One regime — this window is an AI bull market; the edge may not survive a different regime.
  • Short sample — 10 monthly walk-forward points is illustrative; production needs 5–10 years.
  The net-of-cost Sharpe and the per-period rank IC are the most honest figures here.[/dim]""",
        title="[bold cyan]Interpretation[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(summary)
