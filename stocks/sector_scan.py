"""
Sector Scanner — finds the best opportunities across all sectors.
Screens clean energy, nuclear, defense, biotech, fintech, storage, etc.
"""
import yfinance as yf
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Optional, Dict
from rich.table import Table
from rich.console import Console
from rich import box

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.universe import SECTORS, AI_ETFS
from stocks.quant import build_quant_report, QuantReport, format_quant_one_liner
from stocks.parallel import parallel_fetch

console = Console(width=280)


@dataclass
class SectorStock:
    ticker: str
    name: str
    sector_label: str       # which sector bucket we put it in
    current_price: float
    day_change_pct: float
    return_1m: float
    return_6m: float
    return_1y: float
    market_cap_b: float
    pe_ratio: Optional[float]
    forward_pe: Optional[float]
    revenue_growth: Optional[float]
    profit_margin: Optional[float]
    analyst_target: Optional[float]
    upside_to_target: Optional[float]
    week_52_high: float
    pct_from_52w_high: float
    # Extra fields for screener compatibility
    pb_ratio: Optional[float] = None
    ps_ratio: Optional[float] = None
    earnings_growth: Optional[float] = None
    quant: Optional[QuantReport] = None


def _safe(v, default=None):
    if v is None: return default
    try:
        f = float(v)
        return default if (f != f) else f  # NaN check
    except: return default


def fetch_sector_stock(ticker: str, sector_label: str) -> Optional[SectorStock]:
    try:
        t    = yf.Ticker(ticker)
        hist = t.history(period="14mo")
        # Drop bars with no settled close (yfinance often returns today's
        # un-settled bar as a trailing NaN, which would make price/returns NaN).
        hist = hist[hist["Close"].notna()]
        if hist.empty or len(hist) < 60:
            return None

        closes = hist["Close"]
        price  = float(closes.iloc[-1])
        prev   = float(closes.iloc[-2])
        day_c  = round((price - prev) / prev * 100, 2)

        def ret(n):
            if len(closes) > n:
                return round((price / float(closes.iloc[-n-1]) - 1)*100, 2)
            return 0.0

        yr     = closes.tail(252)
        w52h   = float(yr.max())
        pct_h  = round((price - w52h) / w52h * 100, 2)

        info   = t.info
        pe     = _safe(info.get("trailingPE"))
        fwd_pe = _safe(info.get("forwardPE"))
        pb     = _safe(info.get("priceToBook"))
        ps     = _safe(info.get("priceToSalesTrailing12Months"))
        rg     = _safe(info.get("revenueGrowth"))
        eg     = _safe(info.get("earningsGrowth"))
        mg     = _safe(info.get("profitMargins"))
        mc     = _safe(info.get("marketCap"), 0) / 1e9
        tgt    = _safe(info.get("targetMeanPrice"))
        up     = round((tgt - price)/price*100, 1) if tgt else None
        name   = info.get("shortName") or info.get("longName") or ticker

        sd = SectorStock(
            ticker=ticker, name=name, sector_label=sector_label,
            current_price=round(price, 2),
            day_change_pct=day_c,
            return_1m=ret(21), return_6m=ret(126), return_1y=ret(252),
            market_cap_b=round(mc, 1),
            pe_ratio=pe, forward_pe=fwd_pe,
            pb_ratio=pb, ps_ratio=ps,
            revenue_growth=round(rg*100, 1) if rg is not None else None,
            earnings_growth=round(eg*100, 1) if eg is not None else None,
            profit_margin=round(mg*100, 1) if mg is not None else None,
            analyst_target=round(tgt, 2) if tgt else None,
            upside_to_target=up,
            week_52_high=round(w52h, 2),
            pct_from_52w_high=pct_h,
        )

        # Attach quant — pass full OHLCV for technical indicators
        try:
            sd.quant = build_quant_report(sd, closes, hist)
        except Exception:
            try:
                sd.quant = build_quant_report(sd, closes)
            except Exception:
                pass

        return sd
    except Exception as e:
        return None


def scan_all_sectors(sectors: Dict[str, List[str]] = None, top_n: int = 5) -> Dict[str, List[SectorStock]]:
    """
    Scan all sectors, return top N stocks per sector by quant score.
    Also returns a 'best_across_sectors' list.
    """
    if sectors is None:
        sectors = SECTORS

    results: Dict[str, List[SectorStock]] = {}
    all_stocks: List[SectorStock] = []

    # Flatten to (ticker, sector) pairs and fetch every stock concurrently —
    # one shared thread pool across all sectors maximizes overlap of the
    # network waits instead of draining one sector before starting the next.
    jobs = [(ticker, name) for name, tickers in sectors.items() for ticker in tickers]
    total = len(jobs)
    with console.status(f"  Scanning {len(sectors)} sectors ({total} stocks) in parallel...") as status:
        def _progress(done, tot):
            status.update(f"  Scanning {len(sectors)} sectors... {done}/{tot} stocks loaded")
        all_stocks = parallel_fetch(
            jobs,
            lambda job: fetch_sector_stock(job[0], job[1]),
            progress=_progress,
        )

    # Bucket back into sectors, then keep the top N per sector by quant score.
    for sector_name in sectors:
        sector_stocks = [s for s in all_stocks if s.sector_label == sector_name]
        sector_stocks.sort(
            key=lambda x: x.quant.overall_quant_score if x.quant else 0,
            reverse=True
        )
        results[sector_name] = sector_stocks[:top_n]

    results["_all"] = all_stocks
    return results


def scan_etfs() -> List[SectorStock]:
    """Scan all ETFs in universe."""
    name_by_ticker = dict(AI_ETFS)
    with console.status(f"  Scanning {len(AI_ETFS)} ETFs in parallel...") as status:
        def _progress(done, tot):
            status.update(f"  Scanning ETFs... {done}/{tot} loaded")
        etf_stocks = parallel_fetch(
            [t for t, _ in AI_ETFS],
            lambda ticker: fetch_sector_stock(ticker, "ETF"),
            progress=_progress,
        )
    for s in etf_stocks:
        s.name = name_by_ticker.get(s.ticker, s.name)  # use our readable name
    etf_stocks.sort(key=lambda x: x.quant.overall_quant_score if x.quant else 0, reverse=True)
    return etf_stocks


# ── Rich Tables ────────────────────────────────────────────────────────────────

def render_sector_table(sector_name: str, stocks: List[SectorStock]) -> Table:
    """One table per sector showing top picks with full quant data."""
    emoji_map = {
        "Clean Energy & Solar":            "☀️",
        "Nuclear & Grid Storage":           "⚛️",
        "Defense & Aerospace":              "🛡️",
        "Biotech & Healthcare AI":          "🧬",
        "Fintech & Crypto Infrastructure":  "💳",
        "Robotics & Autonomous Systems":    "🤖",
        "Semiconductor Equipment":          "🔬",
        "Data Infrastructure":              "🗄️",
        "AI & Compute Infrastructure":      "🖥️",
        "Cloud & Software Platform":        "☁️",
    }
    emoji = next((v for k, v in emoji_map.items() if k in sector_name), "📊")

    t = Table(
        title=f"{emoji} {sector_name}",
        box=box.ROUNDED, show_lines=True,
        header_style="bold white on dark_blue",
        min_width=200,
    )
    t.add_column("Ticker",    style="bold",    width=7,  no_wrap=True)
    t.add_column("Name",                       width=20, no_wrap=True)
    t.add_column("Price",     justify="right",  width=10)
    t.add_column("1M Ret",    justify="right",  width=9)
    t.add_column("1Y Ret",    justify="right",  width=9)
    t.add_column("PE (ttm)",  justify="right",  width=9)
    t.add_column("Rev Gr%",   justify="right",  width=9)
    t.add_column("Analyst↑",  justify="right",  width=9)
    t.add_column("Tech/100",  justify="right",  width=9)
    t.add_column("Stat/100",  justify="right",  width=9)
    t.add_column("ML/100",    justify="right",  width=8)
    t.add_column("Risk/100",  justify="right",  width=9)
    t.add_column("MACD",      justify="center", width=7)
    t.add_column("Stoch%K",   justify="right",  width=8)
    t.add_column("Hurst",     justify="right",  width=7)
    t.add_column("Kalman-Z",  justify="right",  width=9)
    t.add_column("GARP",      justify="center", width=10)
    t.add_column("Quant",     justify="right",  width=7)
    t.add_column("Signal",                      width=13)

    garp_c = {"CHEAP":"bold green","FAIR":"green","EXPENSIVE":"yellow","VERY_EXPENSIVE":"red","N/A":"dim"}

    sc = {"STRONG_BUY":"bold green","BUY":"green","HOLD":"yellow","SELL":"red","STRONG_SELL":"bold red"}
    gc2 = {"CHEAP":"bold green","FAIR":"green","EXPENSIVE":"yellow","VERY_EXPENSIVE":"red","N/A":"dim"}

    for s in stocks:
        qr = s.quant
        m1c = "green" if s.return_1m >= 0 else "red"
        y1c = "green" if s.return_1y >= 0 else "red"
        sig_c = sc.get(qr.signal_type if qr else "HOLD","white")

        if qr:
            ts  = qr.technical.composite_score
            ss  = qr.statistical.composite_score
            mls = qr.ml_trend.ml_score
            rs  = qr.risk.risk_score
            macd_s = "🟢" if qr.technical.macd.trend_strength in ("BULL","STRONG_BULL") else "🔴" if qr.technical.macd.trend_strength in ("BEAR","STRONG_BEAR") else "⚪"
            stoch_v = qr.technical.stochastic.k_pct
            hu   = qr.statistical.hurst.hurst
            kz   = qr.statistical.kalman.kalman_zscore
            garp = qr.fundamental.garp_rating
            qs   = qr.overall_quant_score
        else:
            ts=ss=mls=rs=stoch_v=hu=kz=qs = 0; macd_s="—"; garp="N/A"

        qs_c  = "green" if qs >= 60 else "yellow" if qs >= 45 else "red"
        gc_color = gc2.get(garp, "white")

        def sc2(v, hi=60, lo=45):
            c = "green" if v>=hi else "yellow" if v>=lo else "red"
            return f"[{c}]{v:.0f}[/{c}]"

        t.add_row(
            s.ticker, s.name[:20], f"${s.current_price:,.2f}",
            f"[{m1c}]{s.return_1m:+.1f}%[/{m1c}]",
            f"[{y1c}]{s.return_1y:+.1f}%[/{y1c}]",
            f"{s.pe_ratio:.1f}x" if s.pe_ratio else "—",
            f"[green]+{s.revenue_growth:.1f}%[/green]" if s.revenue_growth and s.revenue_growth>0 else (f"[red]{s.revenue_growth:.1f}%[/red]" if s.revenue_growth else "—"),
            f"[green]+{s.upside_to_target:.1f}%[/green]" if s.upside_to_target and s.upside_to_target>0 else "—",
            sc2(ts), sc2(ss),
            f"[{'green' if mls>=60 else 'yellow'}]{mls:.0f}[/{'green' if mls>=60 else 'yellow'}]",
            sc2(rs),
            macd_s,
            f"[{'green' if stoch_v<30 else 'red' if stoch_v>70 else 'white'}]{stoch_v:.1f}[/{'green' if stoch_v<30 else 'red' if stoch_v>70 else 'white'}]",
            f"{hu:.3f}" if hu else "—",
            f"[{'green' if kz<-1 else 'red' if kz>1 else 'white'}]{kz:+.2f}[/{'green' if kz<-1 else 'red' if kz>1 else 'white'}]",
            f"[{gc_color}]{garp}[/{gc_color}]",
            sc2(qs),
            f"[{sig_c}]{qr.signal_type if qr else '—'}[/{sig_c}]",
        )
    return t


def render_etf_table(etf_stocks: List[SectorStock]) -> Table:
    """ETF comparison table — always shown."""
    t = Table(
        title="📦 ETF Universe — All Sectors: Tech / Bonds / Commodities / International / Real Estate / Factor",
        box=box.ROUNDED, show_lines=True, header_style="bold magenta",
        min_width=200,
    )
    t.add_column("ETF",      style="bold",    width=7,  no_wrap=True)
    t.add_column("Name",                      width=38, no_wrap=True)
    t.add_column("Price",    justify="right",  width=10)
    t.add_column("Today",    justify="right",  width=9)
    t.add_column("1M Ret",   justify="right",  width=9)
    t.add_column("6M Ret",   justify="right",  width=9)
    t.add_column("1Y Ret",   justify="right",  width=9)
    t.add_column("%Off52H",  justify="right",  width=9)
    t.add_column("Tech/100", justify="right",  width=9)
    t.add_column("Stat/100", justify="right",  width=9)
    t.add_column("ML/100",   justify="right",  width=8)
    t.add_column("Stoch%K",  justify="right",  width=8)
    t.add_column("Hurst",    justify="right",  width=7)
    t.add_column("Kalman-Z", justify="right",  width=9)
    t.add_column("Quant",    justify="right",  width=7)
    t.add_column("Signal",                     width=13)

    sc = {"STRONG_BUY":"bold green","BUY":"green","HOLD":"yellow","SELL":"red","STRONG_SELL":"bold red"}

    def sce(v, hi=60, lo=45):
        c = "green" if v>=hi else "yellow" if v>=lo else "red"
        return f"[{c}]{v:.0f}[/{c}]"

    for s in etf_stocks:
        qr = s.quant
        dc = "green" if s.day_change_pct >= 0 else "red"
        sig_c = sc.get(qr.signal_type if qr else "HOLD", "white")

        if qr:
            ts  = qr.technical.composite_score
            ss  = qr.statistical.composite_score
            mls = qr.ml_trend.ml_score
            stk = qr.technical.stochastic.k_pct
            hu  = qr.statistical.hurst.hurst
            kz  = qr.statistical.kalman.kalman_zscore
            qs  = qr.overall_quant_score
        else:
            ts=ss=mls=stk=hu=kz=qs=0

        t.add_row(
            s.ticker, s.name[:38], f"${s.current_price:,.2f}",
            f"[{dc}]{s.day_change_pct:+.1f}%[/{dc}]",
            f"[{'green' if s.return_1m>=0 else 'red'}]{s.return_1m:+.1f}%[/{'green' if s.return_1m>=0 else 'red'}]",
            f"[{'green' if s.return_6m>=0 else 'red'}]{s.return_6m:+.1f}%[/{'green' if s.return_6m>=0 else 'red'}]",
            f"[{'green' if s.return_1y>=0 else 'red'}]{s.return_1y:+.1f}%[/{'green' if s.return_1y>=0 else 'red'}]",
            f"{s.pct_from_52w_high:.1f}%",
            sce(ts), sce(ss),
            f"[{'green' if mls>=60 else 'yellow'}]{mls:.0f}[/{'green' if mls>=60 else 'yellow'}]",
            f"[{'green' if stk<30 else 'red' if stk>70 else 'white'}]{stk:.1f}[/{'green' if stk<30 else 'red' if stk>70 else 'white'}]",
            f"{hu:.3f}" if hu else "—",
            f"[{'green' if kz<-1 else 'red' if kz>1 else 'white'}]{kz:+.2f}[/{'green' if kz<-1 else 'red' if kz>1 else 'white'}]",
            sce(qs),
            f"[{sig_c}]{qr.signal_type if qr else '—'}[/{sig_c}]",
        )
    return t


def build_sector_context_for_ai(
    sector_results: Dict[str, List[SectorStock]],
    etf_stocks: List[SectorStock],
    hidden_gems: List["HiddenGem"],
) -> str:
    """Build structured context for AI sector analysis."""
    lines = ["=== SECTOR SCAN RESULTS ===\n"]

    for sector, stocks in sector_results.items():
        if sector == "_all" or not stocks:
            continue
        lines.append(f"\n--- {sector} ---")
        for s in stocks:
            qr = s.quant
            lines.append(
                f"{s.ticker} ({s.name[:20]}): price ${s.current_price} | "
                f"analyst_target ${s.analyst_target if s.analyst_target else 'NONE'} "
                f"({s.upside_to_target if s.upside_to_target is not None else 'N/A'}% upside) | "
                f"1Y {s.return_1y:+.1f}% | PE {s.pe_ratio or 'N/A'}x | "
                f"RevGr {s.revenue_growth or 'N/A'}% | "
                f"Quant {qr.overall_quant_score:.0f}/100 | "
                f"GARP {qr.fundamental.garp_rating} | "
                f"P(bull next day) {qr.statistical.markov.prob_bull_tomorrow:.0%} | "
                f"Hurst {qr.statistical.hurst.hurst:.2f}({qr.statistical.hurst.interpretation}) | "
                f"Signal {qr.signal_type}"
                if qr else f"{s.ticker}: price ${s.current_price} | 1Y {s.return_1y:+.1f}%"
            )

    lines.append("\n=== ETF LANDSCAPE (top 20 by quant score) ===")
    top_etfs = sorted(etf_stocks, key=lambda s: s.quant.overall_quant_score if s.quant else 0, reverse=True)[:20]
    for s in top_etfs:
        qr = s.quant
        lines.append(
            f"{s.ticker} ({s.name}): ${s.current_price} | "
            f"1Y {s.return_1y:+.1f}% | 6M {s.return_6m:+.1f}% | "
            f"Quant {qr.overall_quant_score:.0f}/100 | Signal {qr.signal_type}"
            if qr else f"{s.ticker}: {s.return_1y:+.1f}%"
        )

    lines.append("\n=== HIDDEN GEMS (top 12 by quant score) ===")
    top_gems = sorted(hidden_gems, key=lambda g: g.quant.overall_quant_score if g.quant else 0, reverse=True)[:12]
    for g in top_gems:
        qr = g.quant
        short_flag = f" | SHORT_INT={g.short_interest_pct:.0f}%" if g.short_interest_pct and g.short_interest_pct > 10 else ""
        lines.append(
            f"{g.ticker} ({g.name}) [{g.gem_category}]: ${g.current_price} | MktCap ${g.market_cap_b:.1f}B | "
            f"1Y {g.return_1y:+.1f}% | 6M {g.return_6m:+.1f}% | 1M {g.return_1m:+.1f}% | "
            f"RevGr {g.revenue_growth or 'N/A'}% | Margin {g.profit_margin or 'N/A'}% | "
            f"PE {g.pe_ratio or 'N/A'} | Fwd PE {g.forward_pe or 'N/A'} | "
            f"Analyst target ${g.analyst_target or 'N/A'} ({g.upside_to_target or 'N/A'}% upside){short_flag} | "
            f"52W High ${g.week_52_high} ({g.pct_from_52w_high:.1f}% off high) | "
            + (f"Quant {qr.overall_quant_score:.0f}/100 | Signal {qr.signal_type} | "
               f"Hurst {qr.statistical.hurst.hurst:.2f}({qr.statistical.hurst.interpretation})[{qr.statistical.hurst.strategy_fit}] | "
               f"Kalman Z={qr.statistical.kalman.kalman_zscore:+.2f}({qr.statistical.kalman.signal}) | "
               f"RSI={qr.technical.stochastic.k_pct:.0f} | Z20={qr.statistical.mean_reversion.zscore_20d:+.2f} | "
               f"Markov: state={qr.statistical.markov.current_state} P(bull)={qr.statistical.markov.prob_bull_tomorrow:.0%} exp5d={qr.statistical.markov.expected_return_5d:+.1f}% | "
               f"GoldenCross={qr.technical.macd.bullish_cross} | RelStrVsSPY={qr.risk.beta_vs_spy:+.1f}% | "
               f"GARP={qr.fundamental.garp_rating} PEG={qr.fundamental.peg_ratio or 'N/A'} | "
               f"Factors: V={qr.fundamental.value_score}/G={qr.fundamental.growth_score}/Q={qr.fundamental.quality_score}/M={qr.fundamental.momentum_score} | "
               f"Thesis: {g.gem_thesis}"
               if qr else f"Thesis: {g.gem_thesis}")
        )

    return "\n".join(lines)
