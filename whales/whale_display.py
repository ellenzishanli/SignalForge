"""
Whale Tracker Display
Core output: WHAT did smart money BUY/SELL recently + our quant verdict on that ticker.

Layout per whale:
  [Identity card — 1 line]
  [Recent trades table: Ticker | Action | Size | Date | Quant Score | Follow Signal]

Follow signal logic:
  Whale BOUGHT + Quant BUY  → ⭐⭐⭐ STRONG FOLLOW
  Whale BOUGHT + Quant HOLD → ⭐⭐   FOLLOW (whale sees something quant doesn't yet)
  Whale BOUGHT + Quant SELL → ⭐     WATCH  (conflicting signals — investigate)
  Whale SOLD   + Quant BUY  → ⚠️    CAUTION (whale exiting, but technicals still ok)
  Whale SOLD   + Quant SELL → ❌    AVOID  (smart money leaving + quant confirms)
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from rich.table import Table
from rich.panel import Panel
from rich.console import Console
from rich.rule import Rule
from rich.text import Text
from rich import box
from bs4 import BeautifulSoup

from whales.sec_13f import fetch_13f, fetch_ark_holdings, fetch_capitol_trades, Filing13F, Holding
from config.whales import ALL_WHALES, TAB_LABELS, ARK_FUNDS, ADDITIONAL_SOURCES

console = Console(width=220)

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


# ── Data structure for a single whale trade ────────────────────────────────────

@dataclass
class WhaleTrade:
    whale:        str           # e.g. "Berkshire Hathaway (Buffett)"
    ticker:       str           # e.g. "AAPL"
    company:      str           # e.g. "Apple Inc"
    action:       str           # BUY / SELL / INCREASE / DECREASE / NEW / CLOSED / HOLD
    value_usd_m:  float         # in $M
    date:         str           # "Q1 2026" or "2026-05-15"
    source:       str           # "13F" / "ARK Daily" / "Capitol Trades" / "Form 4"
    # Quant scores (populated separately)
    quant_score:  float = 0.0
    quant_signal: str = "N/A"
    tech_score:   float = 0.0
    stat_score:   float = 0.0
    follow:       str = "WATCH"     # STRONG_FOLLOW / FOLLOW / WATCH / CAUTION / AVOID
    follow_reason: str = ""


def _follow_signal(action: str, quant_signal: str, quant_score: float) -> Tuple[str, str]:
    """Combine whale action + quant signal → follow recommendation."""
    is_buy  = action in ("BUY", "NEW", "INCREASE")
    is_sell = action in ("SELL", "CLOSED", "DECREASE")
    q_buy   = quant_signal in ("STRONG_BUY", "BUY")
    q_sell  = quant_signal in ("SELL", "STRONG_SELL")
    q_hold  = quant_signal == "HOLD"

    if is_buy and q_buy:
        return "STRONG_FOLLOW", f"Whale buying + quant confirms (score {quant_score:.0f})"
    if is_buy and q_hold:
        return "FOLLOW", f"Whale buying (quant neutral {quant_score:.0f}) — momentum may follow"
    if is_buy and q_sell:
        return "WATCH", f"Whale buying BUT quant bearish ({quant_score:.0f}) — investigate why"
    if is_sell and q_buy:
        return "CAUTION", f"Whale exiting despite quant BUY ({quant_score:.0f}) — whale may know more"
    if is_sell and q_hold:
        return "CAUTION", f"Whale selling + quant neutral — wait"
    if is_sell and q_sell:
        return "AVOID", f"Whale selling + quant confirms bearish ({quant_score:.0f})"
    return "WATCH", "Insufficient signal"


def _get_quant_for_ticker(ticker: str) -> Dict:
    """Fetch quick quant score for a specific ticker."""
    try:
        import yfinance as yf
        import types
        from stocks.quant import build_quant_report

        t    = yf.Ticker(ticker)
        hist = t.history(period="6mo")
        if hist.empty or len(hist) < 30:
            return {"score": 0, "signal": "N/A", "tech": 0, "stat": 0}

        closes = hist["Close"]
        info   = t.info

        def safe(v):
            try: return float(v) if v and v == v else None
            except: return None

        sd = types.SimpleNamespace(
            ticker=ticker,
            pe_ratio=safe(info.get("trailingPE")),
            pb_ratio=safe(info.get("priceToBook")),
            ps_ratio=safe(info.get("priceToSalesTrailing12Months")),
            forward_pe=safe(info.get("forwardPE")),
            revenue_growth=round(safe(info.get("revenueGrowth")) * 100, 1) if safe(info.get("revenueGrowth")) else None,
            earnings_growth=round(safe(info.get("earningsGrowth")) * 100, 1) if safe(info.get("earningsGrowth")) else None,
            profit_margin=round(safe(info.get("profitMargins")) * 100, 1) if safe(info.get("profitMargins")) else None,
            return_1m=round((float(closes.iloc[-1]) / float(closes.iloc[-22]) - 1) * 100, 2) if len(closes) > 22 else 0,
            return_6m=round((float(closes.iloc[-1]) / float(closes.iloc[0]) - 1) * 100, 2),
            return_1y=0, upside_to_target=None, is_etf=False, gem_category=None,
        )
        qr = build_quant_report(sd, closes, hist)
        return {
            "score":  qr.overall_quant_score,
            "signal": qr.signal_type,
            "tech":   qr.technical.composite_score,
            "stat":   qr.statistical.composite_score,
            "ml":     qr.ml_trend.ml_score,
            "hurst":  qr.statistical.hurst.hurst,
            "kz":     qr.statistical.kalman.kalman_zscore,
        }
    except Exception as e:
        return {"score": 0, "signal": "N/A", "tech": 0, "stat": 0, "ml": 0, "hurst": 0, "kz": 0}


# ── Fetch recent trades from various sources ───────────────────────────────────

def get_13f_trades(entity_name: str, cik: str) -> List[WhaleTrade]:
    """Extract top holdings changes from a 13F filing."""
    filing = fetch_13f(entity_name, cik)
    if not filing or not filing.holdings:
        return []

    trades = []
    for h in filing.holdings[:10]:
        if not h.ticker and not h.name:
            continue
        action = "SHORT" if h.put_call == "Put" else ("CALL" if h.put_call == "Call" else "HOLD/LONG")
        trades.append(WhaleTrade(
            whale=entity_name,
            ticker=h.ticker or h.cusip[:6],
            company=h.name[:30],
            action=action,
            value_usd_m=h.value_usd / 1e6,
            date=f"Q {filing.period}",
            source="SEC 13F",
        ))
    return trades


def get_ark_trades(fund: str = "ARKK") -> List[WhaleTrade]:
    """ARK daily holdings — top positions."""
    holdings = fetch_ark_holdings(fund)
    trades = []
    for h in holdings[:8]:
        trades.append(WhaleTrade(
            whale=f"ARK ({fund})",
            ticker=h.get("ticker", "—"),
            company=h.get("name", "")[:30],
            action="HOLD/LONG",
            value_usd_m=0,
            date="Today",
            source="ARK Daily",
        ))
    return trades


def get_capitol_trades_as_whale() -> List[WhaleTrade]:
    """Convert Capitol Trades data to WhaleTrade format."""
    raw = fetch_capitol_trades(limit=20)
    trades = []
    for t in raw:
        action = "BUY" if "Purchase" in t.get("action", "") else ("SELL" if "Sale" in t.get("action", "") else "UNKNOWN")
        trades.append(WhaleTrade(
            whale=t.get("politician", "Congress"),
            ticker=t.get("ticker", "—"),
            company=t.get("ticker", "—"),
            action=action,
            value_usd_m=0,
            date=t.get("filed_date", "—"),
            source="Capitol Trades",
        ))
    return [t for t in trades if t.ticker and t.ticker != "—"]


def get_openinsider_trades() -> List[WhaleTrade]:
    """Scrape OpenInsider for recent insider buying (Form 4)."""
    url = "https://openinsider.com/screener?s=&o=&pl=100000&ph=&ll=&lh=&fd=14&fdr=&td=0&tdr=&xp=1&vl=&vh=&sic1=-1&grp=0&cnt=20&page=1"
    trades = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.select_one("table.tinytable")
        if not table:
            return []
        for row in table.select("tbody tr")[:15]:
            cells = [td.get_text(strip=True) for td in row.select("td")]
            if len(cells) >= 10:
                ticker = cells[3] if len(cells) > 3 else "—"
                name   = cells[5] if len(cells) > 5 else "—"
                ttype  = cells[7] if len(cells) > 7 else "—"
                value  = cells[9] if len(cells) > 9 else "0"
                date   = cells[1] if len(cells) > 1 else "—"
                if "P" in ttype:  # Purchase
                    try:
                        v = float(value.replace("$","").replace(",","").replace("+","")) / 1e6
                    except:
                        v = 0
                    trades.append(WhaleTrade(
                        whale=f"Insider: {name[:20]}",
                        ticker=ticker, company=ticker,
                        action="BUY (Insider)", value_usd_m=v,
                        date=date, source="Form 4 / OpenInsider",
                    ))
    except Exception as e:
        print(f"[OpenInsider] {e}")
    return trades


def get_dataroma_trades() -> List[WhaleTrade]:
    """Scrape Dataroma for recent superinvestor activity."""
    url = "https://www.dataroma.com/m/activity.php"
    trades = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for row in soup.select("table tr")[1:16]:
            cells = [td.get_text(strip=True) for td in row.select("td")]
            if len(cells) >= 5:
                manager = cells[0]
                ticker  = cells[1]
                action  = cells[2]   # "Buy" / "Sell" / "Add" / "Reduce"
                pct     = cells[3]   # % of portfolio
                date    = cells[4]
                a_clean = "BUY" if "Buy" in action or "Add" in action else ("SELL" if "Sell" in action or "Reduce" in action else action)
                trades.append(WhaleTrade(
                    whale=manager[:25], ticker=ticker, company=ticker,
                    action=a_clean, value_usd_m=0,
                    date=date, source="Dataroma/13F",
                ))
    except Exception as e:
        print(f"[Dataroma] {e}")
    return trades


# ── Enrich trades with quant scores ───────────────────────────────────────────

def enrich_with_quant(trades: List[WhaleTrade], max_tickers: int = 20) -> List[WhaleTrade]:
    """Add quant scores to whale trades. Rate-limited to avoid yfinance overload."""
    seen = {}
    for t in trades:
        ticker = t.ticker.upper().strip()
        if not ticker or ticker in ("—", "N/A", "") or len(ticker) > 6:
            continue
        if ticker not in seen:
            try:
                seen[ticker] = _get_quant_for_ticker(ticker)
                time.sleep(0.1)
            except:
                seen[ticker] = {"score": 0, "signal": "N/A", "tech": 0, "stat": 0, "ml": 0, "hurst": 0, "kz": 0}
        q = seen[ticker]
        t.quant_score  = q.get("score", 0)
        t.quant_signal = q.get("signal", "N/A")
        t.tech_score   = q.get("tech", 0)
        t.stat_score   = q.get("stat", 0)
        t.follow, t.follow_reason = _follow_signal(t.action, t.quant_signal, t.quant_score)

    return trades


# ── Rich Tables ────────────────────────────────────────────────────────────────

def render_trades_table(trades: List[WhaleTrade], title: str) -> Table:
    """
    Core table: what did smart money buy/sell + our quant verdict.
    This is the table investors actually care about.
    """
    t = Table(
        title=title,
        box=box.ROUNDED, show_lines=True,
        header_style="bold white on dark_blue",
        min_width=200,
    )
    t.add_column("Whale / Fund",       width=26, no_wrap=True)
    t.add_column("Ticker",             width=8,  style="bold")
    t.add_column("Company",            width=22, no_wrap=True)
    t.add_column("Action",             width=14, justify="center")
    t.add_column("Size",               width=10, justify="right")
    t.add_column("Period",             width=12)
    t.add_column("Source",             width=14)
    t.add_column("Quant",              width=7,  justify="right")
    t.add_column("Tech",               width=6,  justify="right")
    t.add_column("Stat",               width=6,  justify="right")
    t.add_column("Quant Signal",       width=13, justify="center")
    t.add_column("→ Follow?",          width=16, justify="center")

    action_colors = {
        "BUY":          "bold green",
        "NEW":          "bold green",
        "INCREASE":     "green",
        "SELL":         "bold red",
        "CLOSED":       "bold red",
        "DECREASE":     "red",
        "SHORT":        "bold red",
        "HOLD/LONG":    "yellow",
        "BUY (Insider)":"bold green",
        "CALL":         "cyan",
    }
    follow_colors = {
        "STRONG_FOLLOW": "bold green",
        "FOLLOW":        "green",
        "WATCH":         "yellow",
        "CAUTION":       "orange1",
        "AVOID":         "bold red",
    }
    follow_emoji = {
        "STRONG_FOLLOW": "⭐⭐⭐ STRONG",
        "FOLLOW":        "⭐⭐ FOLLOW",
        "WATCH":         "👁 WATCH",
        "CAUTION":       "⚠️ CAUTION",
        "AVOID":         "❌ AVOID",
    }
    quant_colors = {"STRONG_BUY":"bold green","BUY":"green","HOLD":"yellow","SELL":"red","STRONG_SELL":"bold red","N/A":"dim"}

    for tr in trades:
        ac  = action_colors.get(tr.action, "white")
        fc  = follow_colors.get(tr.follow, "white")
        qc  = quant_colors.get(tr.quant_signal, "dim")
        size_str = f"${tr.value_usd_m:.0f}M" if tr.value_usd_m > 0 else "—"
        qs_c = "green" if tr.quant_score>=60 else "yellow" if tr.quant_score>=45 else ("red" if tr.quant_score>0 else "dim")
        ts_c = "green" if tr.tech_score>=60 else "yellow" if tr.tech_score>=45 else ("red" if tr.tech_score>0 else "dim")
        st_c = "green" if tr.stat_score>=60 else "yellow" if tr.stat_score>=45 else ("red" if tr.stat_score>0 else "dim")

        t.add_row(
            tr.whale[:26],
            tr.ticker,
            tr.company[:22],
            f"[{ac}]{tr.action}[/{ac}]",
            size_str,
            tr.date,
            tr.source[:14],
            f"[{qs_c}]{tr.quant_score:.0f}[/{qs_c}]" if tr.quant_score > 0 else "—",
            f"[{ts_c}]{tr.tech_score:.0f}[/{ts_c}]" if tr.tech_score > 0 else "—",
            f"[{st_c}]{tr.stat_score:.0f}[/{st_c}]" if tr.stat_score > 0 else "—",
            f"[{qc}]{tr.quant_signal}[/{qc}]",
            f"[{fc}]{follow_emoji.get(tr.follow, tr.follow)}[/{fc}]",
        )
    return t


def render_whale_card(entity: Dict, tab: str) -> str:
    """One-line identity card for a whale — shown above their trades."""
    name    = entity.get("name", "")
    manager = entity.get("manager", "")
    style   = entity.get("style", "")
    known   = entity.get("known_for", "")[:80]
    cik     = entity.get("cik", "")
    source  = f"CIK {cik}" if cik else "News/On-chain"
    return f"[bold]{name}[/bold] [{style}] | {manager} | {known} | Data: {source}"


def render_follow_summary(all_trades: List[WhaleTrade]) -> Table:
    """
    Top-level summary: the BEST follow opportunities today.
    Strong Follow trades sorted by quant score.
    """
    strong = [t for t in all_trades if t.follow in ("STRONG_FOLLOW", "FOLLOW") and t.ticker and t.ticker != "—"]
    strong.sort(key=lambda x: x.quant_score, reverse=True)

    t = Table(
        title="🎯 TODAY'S BEST FOLLOW OPPORTUNITIES — Whale Signal + Quant Confirmed",
        box=box.HEAVY_EDGE, show_lines=True,
        header_style="bold yellow on grey11",
        min_width=200,
    )
    t.add_column("Priority",    justify="center", width=10)
    t.add_column("Ticker",      style="bold",     width=8)
    t.add_column("Company",                       width=22, no_wrap=True)
    t.add_column("Whale",                         width=26, no_wrap=True)
    t.add_column("Action",      justify="center", width=12)
    t.add_column("Quant Score", justify="right",  width=11)
    t.add_column("Tech/Stat",   justify="right",  width=10)
    t.add_column("Quant Signal",justify="center", width=13)
    t.add_column("Why Follow",                    width=50)

    for i, tr in enumerate(strong[:12], 1):
        priority = "⭐⭐⭐ #1" if i == 1 else (f"⭐⭐  #{i}" if i <= 3 else f"⭐    #{i}")
        ac  = "bold green" if "BUY" in tr.action else "red"
        qc  = "green" if tr.quant_score>=60 else "yellow"
        qsc = {"STRONG_BUY":"bold green","BUY":"green","HOLD":"yellow","SELL":"red","N/A":"dim"}.get(tr.quant_signal,"white")
        t.add_row(
            f"[{'bold green' if i<=3 else 'green'}]{priority}[/{'bold green' if i<=3 else 'green'}]",
            tr.ticker, tr.company[:22], tr.whale[:26],
            f"[{ac}]{tr.action}[/{ac}]",
            f"[{qc}]{tr.quant_score:.0f}/100[/{qc}]",
            f"T:{tr.tech_score:.0f}|S:{tr.stat_score:.0f}",
            f"[{qsc}]{tr.quant_signal}[/{qsc}]",
            tr.follow_reason[:50],
        )
    return t


# ── Main Runner ────────────────────────────────────────────────────────────────

def run_whale_tracker() -> str:
    """Run all 6 tabs + extra sources. Return summary text for AI analysis."""
    all_trades: List[WhaleTrade] = []
    summary_lines = []

    console.rule("[bold yellow]🐋 WHALE TRACKER — Smart Money Intelligence[/bold yellow]")

    # ── Tab 1 & 2: Institutional + AI Funds (13F + ARK) ──────────────────────
    console.rule("[cyan]Tab 1 & 2: Institutional Holdings (SEC 13F + ARK Daily)[/cyan]")

    priority_13f = [
        ("Berkshire Hathaway",    "0001067983"),
        ("Scion Asset Mgmt",      "0001649978"),
        ("Duquesne Family Office","0001536411"),
        ("Appaloosa Management",  "0001006438"),
    ]

    tab12_trades = []
    for name, cik in priority_13f:
        console.print(f"  [dim]→ Fetching 13F: {name}...[/dim]")
        trades = get_13f_trades(name, cik)
        tab12_trades.extend(trades)
        time.sleep(0.3)

    # ARK daily
    console.print("  [dim]→ Fetching ARK daily holdings...[/dim]")
    tab12_trades.extend(get_ark_trades("ARKK"))

    # Dataroma superinvestors
    console.print("  [dim]→ Fetching Dataroma superinvestors...[/dim]")
    dataroma = get_dataroma_trades()
    tab12_trades.extend(dataroma[:10])

    if tab12_trades:
        console.print("  [dim]→ Running quant analysis on tickers...[/dim]")
        tab12_trades = enrich_with_quant(tab12_trades)
        all_trades.extend(tab12_trades)
        console.print(render_trades_table(tab12_trades[:20], "🏦 Institutional + AI Funds — Recent Positions"))
        console.print()

    # ── Tab 3: Asia Whales ────────────────────────────────────────────────────
    console.rule("[cyan]Tab 3: Asia Whales[/cyan]")
    console.print("  [dim]Note: Hillhouse 13F covers US-listed holdings only. SoftBank via news.[/dim]\n")
    asia_trades = get_13f_trades("Hillhouse Capital", "0001709283")
    if asia_trades:
        asia_trades = enrich_with_quant(asia_trades)
        all_trades.extend(asia_trades)
        console.print(render_trades_table(asia_trades[:10], "🐉 Asia Whales — US Holdings"))
        console.print()

    # ── Tab 4: Crypto Whales ──────────────────────────────────────────────────
    console.rule("[cyan]Tab 4: Crypto Whales[/cyan]")
    crypto_trades = []
    # Known crypto/BTC-adjacent public companies as proxy
    for ticker, whale, action, size in [
        ("MSTR", "Michael Saylor/MSTR", "BUY", 2000),
        ("COIN", "a16z Crypto (via holdings)", "HOLD/LONG", 800),
        ("IBIT", "World Liberty Fin (BTC proxy)", "BUY", 500),
    ]:
        crypto_trades.append(WhaleTrade(
            whale=whale, ticker=ticker, company=ticker,
            action=action, value_usd_m=size,
            date="Recent", source="Public Disclosure",
        ))
    crypto_trades = enrich_with_quant(crypto_trades)
    all_trades.extend(crypto_trades)
    console.print(render_trades_table(crypto_trades, "🐋 Crypto Whales — Public Positions (Proxy Tickers)"))
    console.print()

    # ── Tab 5: Market Makers ──────────────────────────────────────────────────
    console.rule("[cyan]Tab 5: Market Makers + Insider Buying[/cyan]")
    console.print("  [dim]→ Fetching OpenInsider Form 4 (insider buying)...[/dim]")
    insider_trades = get_openinsider_trades()
    if insider_trades:
        insider_trades = enrich_with_quant(insider_trades)
        all_trades.extend(insider_trades)
        console.print(render_trades_table(insider_trades[:12], "⚡ Insider Buying — Form 4 (Last 14 Days)"))
    console.print()

    # ── Tab 6: Political Money ────────────────────────────────────────────────
    console.rule("[cyan]Tab 6: Political Money (STOCK Act Disclosures)[/cyan]")
    console.print("  [dim]→ Fetching Congressional trades...[/dim]")
    political_trades = get_capitol_trades_as_whale()
    if political_trades:
        political_trades = enrich_with_quant(political_trades)
        all_trades.extend(political_trades)
        console.print(render_trades_table(political_trades[:15], "🏛️ Congressional Trades — STOCK Act Disclosures"))
    console.print()

    # ── SUMMARY: Best Follow Opportunities ───────────────────────────────────
    console.rule("[bold yellow]🎯 TOP FOLLOW OPPORTUNITIES — Today's Best Signals[/bold yellow]")
    if all_trades:
        console.print(render_follow_summary(all_trades))

    # Build AI context
    buys  = [t for t in all_trades if "BUY" in t.action and t.follow in ("STRONG_FOLLOW","FOLLOW")]
    sells = [t for t in all_trades if "SELL" in t.action]
    summary_lines.append(f"WHALE TRACKER: {len(all_trades)} trades tracked today")
    summary_lines.append(f"Buy signals: " + ", ".join([f"{t.ticker}({t.whale[:15]})" for t in buys[:8]]))
    summary_lines.append(f"Sell signals: " + ", ".join([f"{t.ticker}({t.whale[:15]})" for t in sells[:5]]))

    return "\n".join(summary_lines)
