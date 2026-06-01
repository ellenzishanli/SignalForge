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
    else:
        strategy_sharpe = float("nan")
        strategy_mean_ret = float("nan")
        strategy_win_rate = float("nan")

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
    t2.add_row("BUY+ Sharpe (annualized)",
               f"[{sharpe_color}]{strategy_sharpe:.2f}[/{sharpe_color}]" if not np.isnan(strategy_sharpe) else "N/A",
               ">0.5 is reasonable, >1.0 is strong")
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

    # ── Render all tables ──
    console.print(t1)
    console.print()
    console.print(t2)
    console.print()
    console.print(t3)
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

  [dim]Note: 10 months of walk-forward data is a short sample. These results are illustrative.
  A production system would use 5–10 years of data and proper transaction cost modeling.[/dim]""",
        title="[bold cyan]Interpretation[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(summary)
