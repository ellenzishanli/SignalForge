"""
Hidden Gems Scanner
Finds under-the-radar, small/mid-cap, recent IPO, and overlooked stocks.
These are NOT the obvious FAANG plays — these are the asymmetric bets.
"""
import yfinance as yf
import numpy as np
from dataclasses import dataclass
from typing import List, Optional
from rich.table import Table
from rich.console import Console
from rich import box

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config.universe import HIDDEN_GEMS as HIDDEN_GEM_TICKERS
from stocks.quant import build_quant_report, QuantReport

console = Console(width=280)


@dataclass
class HiddenGem:
    ticker: str
    name: str
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
    # Fields for quant compat
    pb_ratio: Optional[float]
    ps_ratio: Optional[float]
    earnings_growth: Optional[float]
    short_interest_pct: Optional[float]  # % of float sold short
    gem_thesis: str           # why this is interesting
    gem_category: str         # Quantum | Space | Nuclear | AI-small | Biotech | etc.
    quant: Optional[QuantReport] = None


GEM_METADATA = {
    # Quantum Computing
    "IONQ":  ("Quantum Computing", "Pure-play trapped-ion quantum; IBM/Google competitor; IonQ trapped-ion tech most hardware-ready"),
    "RGTI":  ("Quantum Computing", "Superconducting qubits; cheaper than IBM; strong gov't contracts"),
    "QUBT":  ("Quantum Computing", "Quantum optimization SaaS; no hardware risk; profitable path clearer"),
    "ARQQ":  ("Quantum Crypto",   "Satellite-based quantum encryption; only public pure-play; UK gov backing"),
    # Space
    "ASTS":  ("Space",  "Building space-based 4G/5G — no cell towers needed; AT&T/Verizon partnerships; massive TAM"),
    "RKLB":  ("Space",  "Rocket Lab: small satellite launch + space systems; profitable earlier than SpaceX; DARPA contracts"),
    "LUNR":  ("Space",  "NASA's commercial lunar delivery partner; only 2 companies chosen; no competition"),
    "RDW":   ("Space",  "Space manufacturing & solar power satellites; US Space Force supplier"),
    # Nuclear
    "OKLO":  ("Nuclear", "Sam Altman-backed micro reactor; OpenAI signed power purchase agreement; NRC under review"),
    "NNE":   ("Nuclear", "Ultra-small mobile nuclear; military/remote applications; <$1B market cap speculative"),
    "SMR":   ("Nuclear", "Only NRC-approved SMR design (VOYGR); NuScale; utilities signing LOIs for 2030 deployments"),
    "NRGV":  ("Energy Storage", "Gravity energy storage towers (no lithium); utility-scale; first commercial projects live"),
    # AI Infrastructure (smaller)
    "SMCI":  ("AI Infra", "AI server racks; key NVIDIA partner; >30% revenue growth; historically lower PE than peers"),
    "SOUN":  ("AI Voice", "SoundHound: voice AI for restaurants, cars, hospitals; Nvidia invested; <$3B mkt cap"),
    "BBAI":  ("Defense AI", "BigBear.ai: AI analytics for DoD & intelligence agencies; classified revenue upside"),
    "GFAI":  ("Robotics", "Guardforce AI: security robots in Asia; sub-$100M market cap — high risk/reward"),
    # Biotech AI
    "RXRX":  ("Biotech AI",  "Recursion: AI drug discovery; Nvidia invested $50M; partnered w/ Roche & Bayer; large pipeline"),
    "SDGR":  ("Biotech AI",  "Schrödinger: physics-based molecular simulation; Pfizer, BMS, Novartis as clients"),
    "BEAM":  ("Gene Editing", "Beam Therapeutics: base editing (more precise than CRISPR); multiple IND filings"),
    "PACB":  ("Genomics",    "PacBio: long-read DNA sequencing; AI-powered; competes with Illumina monopoly"),
    # Fintech
    "UPST":  ("Fintech AI", "AI credit underwriting; better default prediction than FICO; banks adopting; high beta"),
    "AFRM":  ("Fintech",    "Affirm: BNPL market leader; Apple Pay Later killed → Affirm wins; revenue reaccelerating"),
    "HOOD":  ("Fintech",    "Robinhood: expanding into crypto, credit card, AI; 23M+ funded accounts; Gen Z demographic"),
    # Air Mobility
    "JOBY":  ("eVTOL", "Joby: Toyota-backed air taxi; FAA certification nearest of any eVTOL; $1B+ cash"),
    "ACHR":  ("eVTOL", "Archer Aviation: United Airlines partnership; $213M DoD contract; 2025 commercial target"),
    # Defense Tech
    "KTOS":  ("Defense Tech", "Kratos: autonomous drones + hypersonics; Navy, Air Force contracts; low PE vs backlog"),
    "GENI":  ("Sports AI",   "Genius Sports: NFL exclusive data deal; sports betting tailwind; profitable in 2024"),
    # Healthcare
    "DOCS":  ("Healthcare AI", "Doximity: LinkedIn for doctors; 80% net margin; monopoly on physician professional network"),
    "TMDX":  ("Medical Tech",  "TransMedics: AI-powered organ preservation/transport; only FDA-approved system; rapid growth"),
    "EXAI":  ("Biotech AI",    "Exscientia: AI-first pharma; Sanofi partnership; entire pipeline designed by AI"),
}


def _safe(v, default=None):
    if v is None: return default
    try:
        f = float(v)
        return default if (f != f) else f
    except: return default


def _try_enrich(ticker: str) -> dict:
    """Fetch enrichment data, fail silently."""
    try:
        from stocks.data_enrichment import fetch_finviz, fetch_stockanalysis
        fv = fetch_finviz(ticker)
        sa = fetch_stockanalysis(ticker)
        return {**fv, **sa}
    except Exception:
        return {}


def fetch_hidden_gem(ticker: str) -> Optional[HiddenGem]:
    try:
        meta = GEM_METADATA.get(ticker, ("Other", "Under-the-radar pick"))
        gem_category, gem_thesis = meta

        t    = yf.Ticker(ticker)
        hist = t.history(period="14mo")
        if hist.empty or len(hist) < 30:
            return None

        closes = hist["Close"]
        price  = float(closes.iloc[-1])
        prev   = float(closes.iloc[-2])
        day_c  = round((price - prev) / prev * 100, 2)

        def ret(n):
            if len(closes) > n:
                return round((price / float(closes.iloc[-n-1]) - 1)*100, 2)
            return 0.0

        yr   = closes.tail(252)
        w52h = float(yr.max())
        pct_h = round((price - w52h) / w52h * 100, 2)

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
        si     = _safe(info.get("shortPercentOfFloat"))
        name   = info.get("shortName") or info.get("longName") or ticker

        g = HiddenGem(
            ticker=ticker, name=name,
            current_price=round(price, 2), day_change_pct=day_c,
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
            short_interest_pct=round(si*100, 1) if si else None,
            gem_thesis=gem_thesis,
            gem_category=gem_category,
        )

        try:
            g.quant = build_quant_report(g, closes, hist)
        except Exception:
            try:
                g.quant = build_quant_report(g, closes)
            except Exception:
                pass

        # Enrich with Finviz + stockanalysis data
        extra = _try_enrich(ticker)
        if extra.get("short_float_pct") is not None:
            g.short_interest_pct = extra["short_float_pct"]
        if extra.get("analyst_buy_count") is not None:
            total = (extra.get("analyst_buy_count",0) +
                     extra.get("analyst_hold_count",0) +
                     extra.get("analyst_sell_count",0))
            if total > 0:
                # Use enriched analyst consensus to possibly improve upside estimate
                buy_pct = extra["analyst_buy_count"] / total
                if buy_pct > 0.7 and g.upside_to_target is None:
                    g.gem_thesis += f" | {extra['analyst_buy_count']}/{total} analysts BUY"

        return g
    except Exception:
        return None


def scan_hidden_gems(tickers: List[str] = None) -> List[HiddenGem]:
    if tickers is None:
        tickers = HIDDEN_GEM_TICKERS

    gems = []
    with console.status("[cyan]Scanning hidden gems universe...[/cyan]"):
        for ticker in tickers:
            g = fetch_hidden_gem(ticker)
            if g:
                gems.append(g)

    gems.sort(key=lambda x: x.quant.overall_quant_score if x.quant else 0, reverse=True)
    return gems


def render_hidden_gems_table(gems: List[HiddenGem]) -> Table:
    # Split into two sub-tables rendered sequentially for clarity
    # Table 1: Identity + Fundamentals
    # Table 2: Quant sub-scores
    # We return a single combined table with generous widths
    t = Table(
        title="💎 Hidden Gems & Experimental Picks — Under-the-Radar Opportunities",
        box=box.HEAVY_EDGE, show_lines=True,
        header_style="bold yellow on grey23",
        min_width=200,
    )
    t.add_column("Ticker",      style="bold",   width=7,  no_wrap=True)
    t.add_column("Category",                    width=16, no_wrap=True)
    t.add_column("Name",                        width=22, no_wrap=True)
    t.add_column("Price",       justify="right", width=10)
    t.add_column("Mkt Cap",     justify="right", width=9)
    t.add_column("1M Ret",      justify="right", width=9)
    t.add_column("1Y Ret",      justify="right", width=9)
    t.add_column("Rev Gr%",     justify="right", width=9)
    t.add_column("Analyst↑",    justify="right", width=9)
    t.add_column("Short%",      justify="right", width=7)
    t.add_column("Tech/100",    justify="right", width=9)
    t.add_column("Stat/100",    justify="right", width=9)
    t.add_column("ML/100",      justify="right", width=8)
    t.add_column("Stoch%K",     justify="right", width=8)
    t.add_column("MACD",        justify="center",width=6)
    t.add_column("Hurst",       justify="right", width=7)
    t.add_column("Kalman-Z",    justify="right", width=9)
    t.add_column("Quant",       justify="right", width=7)
    t.add_column("Signal",                       width=13)
    t.add_column("Thesis",                       width=40)

    cat_colors = {
        "Quantum Computing":"cyan","Quantum Crypto":"cyan","Space":"blue",
        "Nuclear":"red","Energy Storage":"orange1","AI Infra":"green",
        "AI Voice":"green","Defense AI":"yellow","Robotics":"yellow",
        "Biotech AI":"magenta","Gene Editing":"magenta","Genomics":"magenta",
        "Fintech AI":"green","Fintech":"green","eVTOL":"blue",
        "Defense Tech":"yellow","Sports AI":"white","Healthcare AI":"magenta","Medical Tech":"magenta",
    }
    sig_c = {"STRONG_BUY":"bold green","BUY":"green","HOLD":"yellow","SELL":"red","STRONG_SELL":"bold red"}

    for g in gems:
        qr  = g.quant
        m1c = "green" if g.return_1m >= 0 else "red"
        y1c = "green" if g.return_1y >= 0 else "red"
        cc  = cat_colors.get(g.gem_category, "white")

        if qr:
            ts   = qr.technical.composite_score
            ss   = qr.statistical.composite_score
            mls  = qr.ml_trend.ml_score
            stk  = qr.technical.stochastic.k_pct
            macd = "🟢" if qr.technical.macd.trend_strength in ("BULL","STRONG_BULL") else "🔴" if qr.technical.macd.trend_strength in ("BEAR","STRONG_BEAR") else "⚪"
            hu   = qr.statistical.hurst.hurst
            kz   = qr.statistical.kalman.kalman_zscore
            qs   = qr.overall_quant_score
            sv   = qr.signal_type
        else:
            ts=ss=mls=stk=hu=kz=qs=0; macd="—"; sv="HOLD"

        qs_c   = "green" if qs>=60 else "yellow" if qs>=45 else "red"
        sc     = sig_c.get(sv, "white")
        sht    = f"[{'red' if g.short_interest_pct and g.short_interest_pct>15 else 'white'}]{g.short_interest_pct:.0f}%[/{'red' if g.short_interest_pct and g.short_interest_pct>15 else 'white'}]" if g.short_interest_pct else "—"

        def score_cell(v, hi=60, lo=45):
            c = "green" if v>=hi else "yellow" if v>=lo else "red"
            return f"[{c}]{v:.0f}[/{c}]"

        t.add_row(
            g.ticker,
            f"[{cc}]{g.gem_category}[/{cc}]",
            g.name[:22],
            f"${g.current_price:,.2f}",
            f"${g.market_cap_b:.1f}B" if g.market_cap_b >= 0.5 else f"${g.market_cap_b*1000:.0f}M",
            f"[{m1c}]{g.return_1m:+.1f}%[/{m1c}]",
            f"[{y1c}]{g.return_1y:+.1f}%[/{y1c}]",
            f"[green]+{g.revenue_growth:.0f}%[/green]" if g.revenue_growth and g.revenue_growth>0 else "—",
            f"[green]+{g.upside_to_target:.0f}%[/green]" if g.upside_to_target and g.upside_to_target>0 else "—",
            sht,
            score_cell(ts),
            score_cell(ss),
            score_cell(mls),
            f"[{'green' if stk<30 else 'red' if stk>70 else 'white'}]{stk:.0f}[/{'green' if stk<30 else 'red' if stk>70 else 'white'}]",
            macd,
            f"{hu:.3f}" if hu else "—",
            f"[{'green' if kz<-1 else 'red' if kz>1 else 'white'}]{kz:+.2f}[/{'green' if kz<-1 else 'red' if kz>1 else 'white'}]",
            score_cell(qs),
            f"[{sc}]{sv}[/{sc}]",
            g.gem_thesis[:40],
        )

    return t
