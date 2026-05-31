"""
AI Basket Stock Screener — Three-Layer Analysis
Layer 1: Full Dashboard (all stocks, sorted by quant score)
Layer 2: Discount Signals (short-term pullback + strong fundamentals)
Layer 3: Value/GARP Picks (don't need to be down — just undervalued + growing)
"""
import yfinance as yf
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from rich.console import Console
from rich.table import Table
from rich import box
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.settings import AI_BASKET_STOCKS, AI_ETFS, STOCK_SCREEN, DASHBOARD_CORE
from stocks.quant import build_quant_report, QuantReport, format_quant_one_liner

console = Console()


@dataclass
class StockData:
    """Full data snapshot for a single stock / 单只股票完整数据快照."""
    ticker: str
    name: str
    current_price: float
    day_change_pct: float
    consecutive_down_days: int
    return_1w: float
    return_1m: float
    return_6m: float
    return_1y: float
    pe_ratio: Optional[float]
    forward_pe: Optional[float]
    pb_ratio: Optional[float]
    ps_ratio: Optional[float]
    revenue_growth: Optional[float]   # YoY %
    earnings_growth: Optional[float]  # YoY %
    profit_margin: Optional[float]    # %
    market_cap_b: float
    week_52_high: float
    week_52_low: float
    pct_from_52w_high: float
    analyst_target: Optional[float]
    upside_to_target: Optional[float]
    sector: str
    is_etf: bool = False
    quant: Optional[QuantReport] = field(default=None, repr=False)


@dataclass
class DiscountSignal:
    """Stock with short-term pullback + strong medium/long-term growth."""
    stock: StockData
    triggered_by: str
    discount_score: float
    conviction: str


@dataclass
class ValuePick:
    """GARP / Value pick — no dip required, just good fundamentals + quant score."""
    stock: StockData
    garp_rating: str          # CHEAP | FAIR
    peg_ratio: Optional[float]
    quant_score: float
    value_thesis: str         # one-line thesis


def _safe(val, default=None):
    if val is None: return default
    try:
        f = float(val)
        return default if np.isnan(f) else f
    except (TypeError, ValueError):
        return default


def fetch_stock_data(ticker: str, is_etf: bool = False) -> Optional[StockData]:
    """Fetch full fundamental + technical + quant data for one stock."""
    try:
        stock = yf.Ticker(ticker)
        hist  = stock.history(period="14mo")
        if hist.empty or len(hist) < 60:
            return None

        closes = hist["Close"]
        price  = float(closes.iloc[-1])
        prev   = float(closes.iloc[-2])
        day_chg = round((price - prev) / prev * 100, 2)

        # Consecutive down days
        consec = 0
        for i in range(len(closes)-1, 0, -1):
            if closes.iloc[i] < closes.iloc[i-1]: consec += 1
            else: break

        def ret(n):
            idx = max(0, len(closes)-n-1)
            old = float(closes.iloc[idx])
            return round((price-old)/old*100, 2) if old else 0.0

        yr_data  = closes.tail(252)
        w52_high = float(yr_data.max())
        w52_low  = float(yr_data.min())
        pct_off  = round((price - w52_high) / w52_high * 100, 2)

        info = stock.info
        pe      = _safe(info.get("trailingPE"))
        fwd_pe  = _safe(info.get("forwardPE"))
        pb      = _safe(info.get("priceToBook"))
        ps      = _safe(info.get("priceToSalesTrailing12Months"))
        rev_gr  = _safe(info.get("revenueGrowth"))
        earn_gr = _safe(info.get("earningsGrowth"))
        margin  = _safe(info.get("profitMargins"))
        mkt_cap = _safe(info.get("marketCap"), 0) / 1e9
        target  = _safe(info.get("targetMeanPrice"))
        upside  = round((target-price)/price*100, 1) if target else None
        name    = info.get("shortName") or info.get("longName") or ticker
        sector  = info.get("sector") or ("ETF" if is_etf else "Technology")

        sd = StockData(
            ticker=ticker, name=name,
            current_price=round(price,2),
            day_change_pct=day_chg,
            consecutive_down_days=consec,
            return_1w=ret(5), return_1m=ret(21),
            return_6m=ret(126), return_1y=ret(252),
            pe_ratio=pe, forward_pe=fwd_pe,
            pb_ratio=pb, ps_ratio=ps,
            revenue_growth=round(rev_gr*100,1) if rev_gr is not None else None,
            earnings_growth=round(earn_gr*100,1) if earn_gr is not None else None,
            profit_margin=round(margin*100,1) if margin is not None else None,
            market_cap_b=round(mkt_cap,1),
            week_52_high=round(w52_high,2), week_52_low=round(w52_low,2),
            pct_from_52w_high=pct_off,
            analyst_target=round(target,2) if target else None,
            upside_to_target=upside,
            sector=sector, is_etf=is_etf,
        )

        # Attach quant report
        try:
            sd.quant = build_quant_report(sd, closes)
        except Exception:
            sd.quant = None

        return sd
    except Exception as e:
        print(f"[Screener] Error fetching {ticker}: {e}")
        return None


def screen_all(include_etfs: bool = True) -> Dict:
    """
    Fetch all stocks, then produce three layers:
    1. all_stocks — full universe for dashboard
    2. signals — discount/dip + growth signals
    3. value_picks — GARP / fundamental value picks (no dip required)
    """
    cfg = STOCK_SCREEN
    tickers = [(t, False) for t in AI_BASKET_STOCKS]
    if include_etfs:
        tickers += [(t, True) for t in AI_ETFS]

    all_stocks: List[StockData] = []
    signals: List[DiscountSignal] = []
    value_picks: List[ValuePick] = []

    seen_value = set()

    with console.status("[cyan]Fetching market data for all stocks + ETFs...[/cyan]"):
        for ticker, is_etf in tickers:
            sd = fetch_stock_data(ticker, is_etf)
            if sd is None:
                continue
            all_stocks.append(sd)

            # ── Layer 2: Discount Signals (dip + growth) ─────────────
            big_drop    = sd.day_change_pct <= cfg["min_single_day_drop_pct"]
            consec_down = sd.consecutive_down_days >= cfg["min_consecutive_down_days"]

            if big_drop or consec_down:
                growth_ok = sum([
                    sd.return_1m  >= cfg["min_growth_1m_pct"],
                    sd.return_6m  >= cfg["min_growth_6m_pct"],
                    sd.return_1y  >= cfg["min_growth_1y_pct"],
                ]) >= 2
                if growth_ok:
                    dip_score  = abs(sd.day_change_pct)*0.4 + sd.consecutive_down_days*0.6
                    grw_score  = (max(sd.return_1m,0)*0.2 + max(sd.return_6m,0)*0.3 + max(sd.return_1y,0)*0.5) / 100
                    disc_score = round(dip_score * (1 + grw_score), 2)
                    if sd.upside_to_target and sd.upside_to_target > 15:
                        disc_score += 2.0
                    if disc_score >= 12 and sd.return_1y >= 30: conviction = "HIGH"
                    elif disc_score >= 6: conviction = "MEDIUM"
                    else: conviction = "LOW"
                    triggered = "both" if big_drop and consec_down else ("big_drop" if big_drop else "consecutive_down")
                    signals.append(DiscountSignal(stock=sd, triggered_by=triggered,
                                                  discount_score=disc_score, conviction=conviction))

            # ── Layer 3: Value / GARP Picks (no dip required) ────────
            if sd.quant and ticker not in seen_value:
                qr = sd.quant
                # Criteria: quant score ≥ 55 AND (GARP cheap/fair OR oversold OR strong growth)
                garp_ok     = qr.fundamental.garp_rating in ("CHEAP", "FAIR")
                oversold_ok = qr.mean_reversion.is_oversold
                growth_ok_v = (sd.revenue_growth or 0) > 15 and qr.fundamental.composite_score >= 6
                quant_ok    = qr.overall_quant_score >= 55

                if quant_ok and (garp_ok or oversold_ok or growth_ok_v):
                    # Build thesis
                    parts = []
                    if qr.fundamental.peg_ratio and qr.fundamental.peg_ratio < 1.5:
                        parts.append(f"PEG={qr.fundamental.peg_ratio:.2f}")
                    if oversold_ok:
                        parts.append(f"oversold (Z={qr.statistical.mean_reversion.zscore_20d:+.1f})")
                    if sd.upside_to_target and sd.upside_to_target > 15:
                        parts.append(f"+{sd.upside_to_target:.0f}% analyst upside")
                    if sd.revenue_growth and sd.revenue_growth > 20:
                        parts.append(f"{sd.revenue_growth:.0f}% revenue growth")
                    if qr.technical.macd.bullish_cross:
                        parts.append("golden cross")

                    thesis = " | ".join(parts) if parts else "Strong quant composite"
                    value_picks.append(ValuePick(
                        stock=sd,
                        garp_rating=qr.fundamental.garp_rating,
                        peg_ratio=qr.fundamental.peg_ratio,
                        quant_score=qr.overall_quant_score,
                        value_thesis=thesis,
                    ))
                    seen_value.add(ticker)

    signals.sort(key=lambda x: x.discount_score, reverse=True)
    value_picks.sort(key=lambda x: x.quant_score, reverse=True)
    return {"all_stocks": all_stocks, "signals": signals, "value_picks": value_picks}


# ── Rich Tables ────────────────────────────────────────────────────────────────

def render_dashboard(all_stocks: List[StockData]) -> Table:
    """Core stock dashboard table sorted by 1Y return."""
    stocks = sorted(
        [s for s in all_stocks if s.ticker in DASHBOARD_CORE],
        key=lambda x: x.return_1y, reverse=True
    )
    t = Table(
        title="📊 AI Basket Core Dashboard",
        box=box.ROUNDED, show_lines=True, header_style="bold cyan",
    )
    t.add_column("Ticker",    style="bold", width=7)
    t.add_column("Company",   width=18, no_wrap=True)
    t.add_column("Price",     justify="right", width=9)
    t.add_column("Today",     justify="right", width=8)
    t.add_column("1M",        justify="right", width=7)
    t.add_column("6M",        justify="right", width=7)
    t.add_column("1Y",        justify="right", width=8)
    t.add_column("PE",        justify="right", width=7)
    t.add_column("Fwd PE",    justify="right", width=7)
    t.add_column("PB",        justify="right", width=6)
    t.add_column("RevGrowth", justify="right", width=10)
    t.add_column("Margin",    justify="right", width=8)
    t.add_column("%Off52H",   justify="right", width=9)
    t.add_column("Upside",    justify="right", width=8)
    t.add_column("Quant",     justify="right", width=7)

    def c(val, positive_good=True):
        if val is None: return "—"
        color = ("green" if val >= 0 else "red") if positive_good else ("red" if val >= 0 else "green")
        return f"[{color}]{val:+.1f}%[/{color}]"

    for s in stocks:
        qs = f"{s.quant.overall_quant_score:.0f}" if s.quant else "—"
        qs_color = "green" if s.quant and s.quant.overall_quant_score >= 60 else "yellow" if s.quant and s.quant.overall_quant_score >= 45 else "red"
        t.add_row(
            s.ticker, s.name[:18], f"${s.current_price:,.2f}",
            c(s.day_change_pct), c(s.return_1m), c(s.return_6m), c(s.return_1y),
            f"{s.pe_ratio:.1f}x" if s.pe_ratio else "—",
            f"{s.forward_pe:.1f}x" if s.forward_pe else "—",
            f"{s.pb_ratio:.1f}x" if s.pb_ratio else "—",
            f"[green]{s.revenue_growth:+.0f}%[/green]" if s.revenue_growth and s.revenue_growth > 0 else (f"[red]{s.revenue_growth:.0f}%[/red]" if s.revenue_growth else "—"),
            f"{s.profit_margin:.1f}%" if s.profit_margin else "—",
            f"[{'red' if s.pct_from_52w_high < -20 else 'yellow' if s.pct_from_52w_high < -10 else 'white'}]{s.pct_from_52w_high:.1f}%[/{'red' if s.pct_from_52w_high < -20 else 'yellow' if s.pct_from_52w_high < -10 else 'white'}]",
            f"[green]+{s.upside_to_target:.0f}%[/green]" if s.upside_to_target and s.upside_to_target > 0 else "—",
            f"[{qs_color}]{qs}[/{qs_color}]",
        )
    return t


def render_etf_table(all_stocks: List[StockData]) -> Table:
    etfs = sorted([s for s in all_stocks if s.is_etf], key=lambda x: x.return_1y, reverse=True)
    t = Table(title="📦 AI Theme ETF Comparison", box=box.ROUNDED, show_lines=True, header_style="bold magenta")
    t.add_column("ETF",    style="bold", width=7)
    t.add_column("Name",   width=32)
    t.add_column("Price",  justify="right", width=9)
    t.add_column("Today",  justify="right", width=8)
    t.add_column("1M",     justify="right", width=7)
    t.add_column("6M",     justify="right", width=7)
    t.add_column("1Y",     justify="right", width=8)
    t.add_column("%Off52H",justify="right", width=9)
    t.add_column("Quant",  justify="right", width=7)
    for s in etfs:
        dc = "green" if s.day_change_pct >= 0 else "red"
        qs = f"{s.quant.overall_quant_score:.0f}" if s.quant else "—"
        t.add_row(
            s.ticker, s.name[:32], f"${s.current_price:,.2f}",
            f"[{dc}]{s.day_change_pct:+.1f}%[/{dc}]",
            f"[{'green' if s.return_1m>=0 else 'red'}]{s.return_1m:+.1f}%[/{'green' if s.return_1m>=0 else 'red'}]",
            f"[{'green' if s.return_6m>=0 else 'red'}]{s.return_6m:+.1f}%[/{'green' if s.return_6m>=0 else 'red'}]",
            f"[{'green' if s.return_1y>=0 else 'red'}]{s.return_1y:+.1f}%[/{'green' if s.return_1y>=0 else 'red'}]",
            f"{s.pct_from_52w_high:.1f}%", qs,
        )
    return t


def render_signals_table(signals: List[DiscountSignal]) -> Table:
    t = Table(title="🎯 Buy-at-Discount Signals", box=box.HEAVY_EDGE, show_lines=True, header_style="bold green")
    t.add_column("Conviction", justify="center", width=10)
    t.add_column("Ticker",  style="bold", width=7)
    t.add_column("Company", width=18, no_wrap=True)
    t.add_column("Price",   justify="right", width=9)
    t.add_column("Today",   justify="right", width=8)
    t.add_column("Days↓",   justify="center", width=6)
    t.add_column("1M",      justify="right", width=7)
    t.add_column("1Y",      justify="right", width=8)
    t.add_column("RSI",     justify="right", width=6)
    t.add_column("Z-score", justify="right", width=8)
    t.add_column("PE",      justify="right", width=7)
    t.add_column("GARP",    justify="center", width=9)
    t.add_column("Upside",  justify="right", width=8)
    t.add_column("Score",   justify="right", width=7)

    styles = {"HIGH": "bold green", "MEDIUM": "yellow", "LOW": "dim"}
    for sig in signals:
        s  = sig.stock
        qr = s.quant
        t.add_row(
            f"[{styles[sig.conviction]}]{sig.conviction}[/{styles[sig.conviction]}]",
            s.ticker, s.name[:18], f"${s.current_price:,.2f}",
            f"[red]{s.day_change_pct:+.1f}%[/red]",
            f"[red]{s.consecutive_down_days}d[/red]",
            f"[{'green' if s.return_1m>0 else 'red'}]{s.return_1m:+.1f}%[/{'green' if s.return_1m>0 else 'red'}]",
            f"[{'green' if s.return_1y>0 else 'red'}]{s.return_1y:+.1f}%[/{'green' if s.return_1y>0 else 'red'}]",
            f"{qr.technical.stochastic.k_pct:.0f}" if qr else "—",
            f"{qr.statistical.mean_reversion.zscore_20d:+.2f}" if qr else "—",
            f"{s.pe_ratio:.1f}x" if s.pe_ratio else "—",
            f"[green]{qr.fundamental.garp_rating}[/green]" if qr and qr.fundamental.garp_rating in ("CHEAP","FAIR") else (qr.fundamental.garp_rating if qr else "—"),
            f"[green]+{s.upside_to_target:.0f}%[/green]" if s.upside_to_target and s.upside_to_target > 0 else "—",
            f"[bold]{sig.discount_score:.1f}[/bold]",
        )
    return t


def render_value_picks_table(value_picks: List[ValuePick]) -> Table:
    t = Table(title="💎 Value & GARP Picks (No Dip Required)", box=box.ROUNDED, show_lines=True, header_style="bold yellow")
    t.add_column("Ticker",    style="bold", width=7)
    t.add_column("Company",   width=18, no_wrap=True)
    t.add_column("Price",     justify="right", width=9)
    t.add_column("GARP",      justify="center", width=8)
    t.add_column("PEG",       justify="right", width=7)
    t.add_column("Fwd PE",    justify="right", width=8)
    t.add_column("RevGrowth", justify="right", width=10)
    t.add_column("Margin",    justify="right", width=8)
    t.add_column("RSI",       justify="right", width=6)
    t.add_column("Z-score",   justify="right", width=8)
    t.add_column("MA Signal", justify="center", width=10)
    t.add_column("Upside",    justify="right", width=8)
    t.add_column("Quant",     justify="right", width=7)
    t.add_column("Thesis",    width=35)

    garp_colors = {"CHEAP": "bold green", "FAIR": "green", "EXPENSIVE": "yellow", "VERY_EXPENSIVE": "red", "N/A": "dim"}
    for vp in value_picks[:15]:
        s  = vp.stock
        qr = s.quant
        ma_sig = "🟢 GC" if qr and qr.technical.macd.bullish_cross else ("🔴 DC" if qr and qr.technical.macd.bearish_cross else "—")
        gc = garp_colors.get(vp.garp_rating, "white")
        t.add_row(
            s.ticker, s.name[:18], f"${s.current_price:,.2f}",
            f"[{gc}]{vp.garp_rating}[/{gc}]",
            f"{vp.peg_ratio:.2f}" if vp.peg_ratio else "—",
            f"{s.forward_pe:.1f}x" if s.forward_pe else "—",
            f"[green]+{s.revenue_growth:.0f}%[/green]" if s.revenue_growth and s.revenue_growth > 0 else "—",
            f"{s.profit_margin:.1f}%" if s.profit_margin else "—",
            f"{qr.technical.stochastic.k_pct:.0f}" if qr else "—",
            f"{qr.statistical.mean_reversion.zscore_20d:+.2f}" if qr else "—",
            ma_sig,
            f"[green]+{s.upside_to_target:.0f}%[/green]" if s.upside_to_target and s.upside_to_target > 0 else "—",
            f"[bold]{vp.quant_score:.0f}[/bold]",
            vp.value_thesis[:35],
        )
    return t


def build_stock_context_for_ai(
    signals: List[DiscountSignal],
    value_picks: List[ValuePick],
    all_stocks: List[StockData],
) -> str:
    """Build structured context string for AI analysis."""
    lines = []

    lines.append("=== DISCOUNT SIGNALS (Short-term dip + strong fundamentals) ===")
    if signals:
        for sig in signals:
            s  = sig.stock
            qr = s.quant
            lines.append(f"""
{s.ticker} ({s.name}) | Conviction: {sig.conviction} | Discount Score: {sig.discount_score}
  Price: ${s.current_price} | Today: {s.day_change_pct:+.1f}% | Consecutive down days: {s.consecutive_down_days}
  Returns: 1W {s.return_1w:+.1f}% | 1M {s.return_1m:+.1f}% | 6M {s.return_6m:+.1f}% | 1Y {s.return_1y:+.1f}%
  Valuation: PE={s.pe_ratio or 'N/A'} | Fwd PE={s.forward_pe or 'N/A'} | PB={s.pb_ratio or 'N/A'} | PS={s.ps_ratio or 'N/A'}
  Fundamentals: Revenue Growth={s.revenue_growth or 'N/A'}% | Earnings Growth={s.earnings_growth or 'N/A'}% | Net Margin={s.profit_margin or 'N/A'}%
  Technicals: 52W High=${s.week_52_high} | 52W Low=${s.week_52_low} | {s.pct_from_52w_high:.1f}% off 52W high
  Analyst: Target=${s.analyst_target or 'N/A'} | Upside={s.upside_to_target or 'N/A'}%
  Quant: {f'Score={qr.overall_quant_score:.0f}/100 | RSI={qr.technical.stochastic.k_pct:.0f} | Z-score={qr.statistical.mean_reversion.zscore_20d:+.2f} | Markov state={qr.statistical.markov.current_state} | P(bull tomorrow)={qr.statistical.markov.prob_bull_tomorrow:.0%} | GARP={qr.fundamental.garp_rating} | PEG={qr.fundamental.peg_ratio or "N/A"} | {qr.quant_thesis}' if qr else 'N/A'}
""")
    else:
        lines.append("None today.")

    lines.append("\n=== VALUE / GARP PICKS (No dip required — fundamentally attractive) ===")
    if value_picks:
        for vp in value_picks[:10]:
            s  = vp.stock
            qr = s.quant
            lines.append(f"""
{s.ticker} ({s.name}) | GARP: {vp.garp_rating} | PEG: {vp.peg_ratio or 'N/A'} | Quant Score: {vp.quant_score:.0f}/100
  Price: ${s.current_price} | Today: {s.day_change_pct:+.1f}% | 1Y: {s.return_1y:+.1f}%
  Valuation: PE={s.pe_ratio or 'N/A'} | Fwd PE={s.forward_pe or 'N/A'} | PB={s.pb_ratio or 'N/A'}
  Fundamentals: Revenue Growth={s.revenue_growth or 'N/A'}% | Net Margin={s.profit_margin or 'N/A'}%
  Analyst: Target=${s.analyst_target or 'N/A'} | Upside={s.upside_to_target or 'N/A'}%
  Quant signals: {f'RSI={qr.technical.stochastic.k_pct:.0f} | Z={qr.statistical.mean_reversion.zscore_20d:+.2f} | Markov P(bull)={qr.statistical.markov.prob_bull_tomorrow:.0%} | Golden Cross={qr.technical.macd.bullish_cross}' if qr else 'N/A'}
  Thesis: {vp.value_thesis}
""")
    else:
        lines.append("None today.")

    lines.append("\n=== MARKET SNAPSHOT (Core AI Stocks) ===")
    from config.settings import DASHBOARD_CORE
    core = sorted([s for s in all_stocks if s.ticker in DASHBOARD_CORE], key=lambda x: x.return_1y, reverse=True)
    for s in core:
        qr = s.quant
        lines.append(
            f"{s.ticker}: ${s.current_price} | Today {s.day_change_pct:+.1f}% | "
            f"1Y {s.return_1y:+.1f}% | PE {s.pe_ratio or 'N/A'}x | Fwd PE {s.forward_pe or 'N/A'}x | "
            f"RevGrowth {s.revenue_growth or 'N/A'}% | {s.pct_from_52w_high:.1f}% off 52W high | "
            f"Quant {qr.overall_quant_score:.0f}/100" if qr else f"{s.ticker}: ${s.current_price}"
        )

    return "\n".join(lines)
