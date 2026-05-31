"""
Whale Tracker Display
Core output: WHAT did smart money BUY/SELL + our quant verdict → Follow signal.

Follow signal logic:
  Whale BUY  + Quant BUY  → ⭐⭐⭐ STRONG FOLLOW
  Whale BUY  + Quant HOLD → ⭐⭐   FOLLOW
  Whale BUY  + Quant SELL → ⭐     WATCH
  Whale SELL + Quant BUY  → ⚠️    CAUTION
  Whale SELL + Quant SELL → ❌    AVOID
"""
import sys, os, time, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from rich.table import Table
from rich.console import Console
from rich.rule import Rule
from rich import box
from bs4 import BeautifulSoup

from whales.sec_13f import fetch_13f, fetch_ark_holdings, fetch_capitol_trades
from whales.social_signals import (
    fetch_quiverquant_congress, fetch_finviz_insiders,
    fetch_stocktwits_sentiment, fetch_stocktwits_trending,
    fetch_whale_news, fetch_sec_13f_alerts,
)
from config.whales import ALL_WHALES

console = Console(width=220)
WEB_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
SEC_HEADERS = {"User-Agent": "SignalForge research@signalforge.io"}


@dataclass
class WhaleTrade:
    whale:         str
    ticker:        str
    company:       str
    action:        str    # BUY / SELL / INCREASE / DECREASE / HOLD/LONG / SHORT
    value_usd_m:   float  # in $M, 0 if unknown
    date:          str
    source:        str
    quant_score:   float = 0.0
    quant_signal:  str   = "N/A"
    tech_score:    float = 0.0
    stat_score:    float = 0.0
    follow:        str   = "WATCH"
    follow_reason: str   = ""


def _follow_signal(action: str, qs: str, score: float) -> Tuple[str, str]:
    is_buy  = any(x in action for x in ("BUY","NEW","INCREASE","PURCHASE","Purchase"))
    is_sell = any(x in action for x in ("SELL","CLOSED","DECREASE","Sale","sale"))
    q_buy   = qs in ("STRONG_BUY","BUY")
    q_sell  = qs in ("SELL","STRONG_SELL")

    if is_buy  and q_buy:   return "STRONG_FOLLOW", f"Whale buying + quant confirms (score {score:.0f})"
    if is_buy  and not q_sell: return "FOLLOW",     f"Whale buying — quant {qs} ({score:.0f})"
    if is_buy  and q_sell:  return "WATCH",         f"Whale buying but quant bearish ({score:.0f}) — investigate"
    if is_sell and q_buy:   return "CAUTION",       f"Whale exiting despite quant BUY ({score:.0f}) — whale may know more"
    if is_sell and q_sell:  return "AVOID",         f"Whale selling + quant confirms bearish ({score:.0f})"
    return "WATCH", "Insufficient signal"


def _get_quant_for_ticker(ticker: str) -> Dict:
    """Fetch quant score for a ticker. Returns defaults if fails."""
    default = {"score": 0, "signal": "N/A", "tech": 0, "stat": 0}
    try:
        import yfinance as yf, types
        from stocks.quant import build_quant_report

        t    = yf.Ticker(ticker)
        hist = t.history(period="6mo")
        if hist.empty or len(hist) < 30:
            return default
        closes = hist["Close"]
        info   = t.info

        def safe(v):
            try: f = float(v); return None if f != f else f
            except: return None

        rg = safe(info.get("revenueGrowth"))
        eg = safe(info.get("earningsGrowth"))
        mg = safe(info.get("profitMargins"))

        sd = types.SimpleNamespace(
            ticker=ticker,
            pe_ratio=safe(info.get("trailingPE")),
            pb_ratio=safe(info.get("priceToBook")),
            ps_ratio=safe(info.get("priceToSalesTrailing12Months")),
            forward_pe=safe(info.get("forwardPE")),
            revenue_growth=round(rg*100,1) if rg else None,
            earnings_growth=round(eg*100,1) if eg else None,
            profit_margin=round(mg*100,1) if mg else None,
            return_1m=round((float(closes.iloc[-1])/float(closes.iloc[-22])-1)*100,2) if len(closes)>22 else 0,
            return_6m=round((float(closes.iloc[-1])/float(closes.iloc[0])-1)*100,2),
            return_1y=0, upside_to_target=None, is_etf=False, gem_category=None,
        )
        qr = build_quant_report(sd, closes, hist)
        return {
            "score":  qr.overall_quant_score,
            "signal": qr.signal_type,
            "tech":   qr.technical.composite_score,
            "stat":   qr.statistical.composite_score,
        }
    except Exception:
        return default


def enrich_with_quant(trades: List[WhaleTrade]) -> List[WhaleTrade]:
    """Add quant scores to trades. Caches by ticker to avoid re-fetching."""
    cache: Dict[str, Dict] = {}
    for t in trades:
        ticker = t.ticker.upper().strip()
        if not ticker or ticker in ("—","N/A","") or len(ticker) > 6:
            continue
        if ticker not in cache:
            cache[ticker] = _get_quant_for_ticker(ticker)
            time.sleep(0.15)
        q = cache[ticker]
        t.quant_score  = q["score"]
        t.quant_signal = q["signal"]
        t.tech_score   = q["tech"]
        t.stat_score   = q["stat"]
        t.follow, t.follow_reason = _follow_signal(t.action, t.quant_signal, t.quant_score)
    return trades


def deduplicate(trades: List[WhaleTrade], by_ticker_only: bool = False) -> List[WhaleTrade]:
    """Remove exact duplicates.
    by_ticker_only=True → keep best-scored entry per ticker (for summary table).
    by_ticker_only=False → keep one entry per (whale, ticker) pair.
    """
    seen: Dict[str, WhaleTrade] = {}
    for t in trades:
        key = t.ticker.upper() if by_ticker_only else f"{t.whale}|{t.ticker.upper()}"
        if key not in seen or t.quant_score > seen[key].quant_score:
            seen[key] = t
    return sorted(seen.values(), key=lambda x: x.quant_score, reverse=True)


# ── Data fetchers ──────────────────────────────────────────────────────────────

def get_13f_trades(entity_name: str, cik: str) -> List[WhaleTrade]:
    filing = fetch_13f(entity_name, cik)
    if not filing or not filing.holdings:
        return []
    trades = []
    for h in filing.holdings[:12]:
        if not h.name:
            continue
        action = "SHORT" if h.put_call == "Put" else ("CALL" if h.put_call == "Call" else "HOLD/LONG")
        trades.append(WhaleTrade(
            whale=entity_name, ticker=h.ticker or "", company=h.name[:30],
            action=action, value_usd_m=h.value_usd/1e6,
            date=f"Q {filing.period[:7]}", source="SEC 13F",
        ))
    return trades


def get_ark_trades(fund: str = "ARKK") -> List[WhaleTrade]:
    holdings = fetch_ark_holdings(fund)
    return [WhaleTrade(
        whale=f"ARK {fund} (Cathie Wood)", ticker=h.get("ticker",""),
        company=h.get("name","")[:30], action="HOLD/LONG",
        value_usd_m=0, date="Today", source="ARK Daily",
    ) for h in holdings[:8] if h.get("ticker")]


def _load_cik_ticker_map() -> Dict[str, str]:
    """Load SEC's official CIK→ticker map (cached in memory)."""
    try:
        r = requests.get("https://www.sec.gov/files/company_tickers.json",
                         headers=SEC_HEADERS, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return {str(v["cik_str"]).zfill(10): v["ticker"]
                    for v in data.values() if v.get("ticker")}
    except Exception:
        pass
    return {}


def get_sec_form4_insider() -> List[WhaleTrade]:
    """
    Fetch recent insider buying (Form 4) from SEC EDGAR.
    Strategy: search EDGAR full-text for Form 4 filings, get the issuer CIK
    from the filing XML, look up the ticker from SEC's official CIK→ticker map.
    """
    trades: List[WhaleTrade] = []

    # Step 1: load SEC's official ticker map
    cik_to_ticker = _load_cik_ticker_map()

    # Step 2: search EDGAR for Form 4 filings over last 90 days
    from datetime import datetime, timedelta
    start_dt = (datetime.today() - timedelta(days=90)).strftime("%Y-%m-%d")
    try:
        url = (f"https://efts.sec.gov/LATEST/search-index?q=%22P+-+Purchase%22"
               f"&forms=4&dateRange=custom&startdt={start_dt}&category=form-type")
        r = requests.get(url, headers=SEC_HEADERS, timeout=12)
        hits = r.json().get("hits", {}).get("hits", []) if r.status_code == 200 else []

        seen_tickers: set = set()
        for hit in hits[:40]:
            s = hit.get("_source", {})
            adsh = s.get("adsh", "")
            date = s.get("file_date", "")[:10]
            filer = (s.get("display_names") or ["Unknown"])[0][:22]

            if not adsh:
                continue

            # Step 3: fetch filing index to find issuer CIK (different from filer CIK)
            try:
                acc = adsh.replace("-", "")
                # The filer entity_id is the reporting person's CIK
                filer_cik = str(s.get("entity_id", "")).zfill(10)
                # Fetch the actual Form 4 XML to get the issuer CIK
                base = f"https://www.sec.gov/Archives/edgar/data/{filer_cik.lstrip('0')}/{acc}/"
                idx_r = requests.get(base, headers=SEC_HEADERS, timeout=6)
                if idx_r.status_code != 200:
                    continue
                # Find the .xml file in the index
                xml_link = re.search(r'href="([^"]+\.xml)"', idx_r.text)
                if not xml_link:
                    continue
                xml_url = "https://www.sec.gov" + xml_link.group(1) if xml_link.group(1).startswith("/") else base + xml_link.group(1)
                xr = requests.get(xml_url, headers=SEC_HEADERS, timeout=8)
                if xr.status_code != 200:
                    continue
                # Extract issuerCik from the Form 4 XML
                issuer_cik_m = re.search(r"<issuerCik>(\d+)</issuerCik>", xr.text)
                issuer_name_m = re.search(r"<issuerName>([^<]+)</issuerName>", xr.text)
                if not issuer_cik_m:
                    continue
                issuer_cik = issuer_cik_m.group(1).zfill(10)
                issuer_name = issuer_name_m.group(1) if issuer_name_m else issuer_cik
                ticker = cik_to_ticker.get(issuer_cik, "")
                if not ticker or ticker in seen_tickers:
                    continue
                seen_tickers.add(ticker)
                trades.append(WhaleTrade(
                    whale=f"Insider: {filer}",
                    ticker=ticker, company=issuer_name[:28],
                    action="BUY (Insider)", value_usd_m=0,
                    date=date, source="SEC Form 4",
                ))
                if len(trades) >= 10:
                    break
                time.sleep(0.1)
            except Exception:
                continue
    except Exception as e:
        print(f"  [Form 4] {e}")

    return trades[:12]


def get_dataroma_trades() -> List[WhaleTrade]:
    """Dataroma superinvestor activity — recent buys/sells."""
    trades = []
    try:
        r = requests.get("https://www.dataroma.com/m/activity.php",
                         headers=WEB_HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for row in soup.select("table tr")[1:20]:
            cells = [td.get_text(strip=True) for td in row.select("td")]
            if len(cells) < 4:
                continue
            manager = cells[0]
            ticker  = re.sub(r"[^A-Z\.]","", cells[1].upper())[:5]
            action  = cells[2]
            date    = cells[4] if len(cells) > 4 else "—"
            if not ticker:
                continue
            a = "BUY" if any(x in action for x in ("Buy","Add")) else ("SELL" if any(x in action for x in ("Sell","Reduce")) else action)
            trades.append(WhaleTrade(
                whale=manager[:25], ticker=ticker, company=ticker,
                action=a, value_usd_m=0, date=date, source="Dataroma/13F",
            ))
    except Exception as e:
        print(f"  [Dataroma] {e}")
    return trades[:12]


def get_capitol_trades_as_whale() -> List[WhaleTrade]:
    raw = fetch_capitol_trades(limit=20)
    trades = []
    for t in raw:
        action = "BUY" if "Purchase" in t.get("action","") else ("SELL" if "Sale" in t.get("action","") else t.get("action","—"))
        ticker = re.sub(r"[^A-Z]","", t.get("ticker","").upper())[:5]
        if not ticker:
            continue
        trades.append(WhaleTrade(
            whale=t.get("politician","Congress")[:25],
            ticker=ticker, company=t.get("company", ticker)[:25],
            action=action, value_usd_m=0,
            date=t.get("filed_date","—"), source="Capitol Trades",
        ))
    return trades


# ── Rich Tables ────────────────────────────────────────────────────────────────

def render_trades_table(trades: List[WhaleTrade], title: str) -> Table:
    t = Table(title=title, box=box.ROUNDED, show_lines=True,
              header_style="bold white on dark_blue", min_width=200)
    t.add_column("Whale / Fund",    width=26, no_wrap=True)
    t.add_column("Ticker",          width=8,  style="bold")
    t.add_column("Company",         width=22, no_wrap=True)
    t.add_column("Action",          width=14, justify="center")
    t.add_column("Size",            width=10, justify="right")
    t.add_column("Period",          width=12)
    t.add_column("Source",          width=14)
    t.add_column("Quant/100",       width=9,  justify="right")
    t.add_column("Tech",            width=6,  justify="right")
    t.add_column("Stat",            width=6,  justify="right")
    t.add_column("Signal",          width=13, justify="center")
    t.add_column("→ Follow?",       width=16, justify="center")

    ac = {"BUY":"bold green","NEW":"bold green","INCREASE":"green","Purchase":"bold green",
          "SELL":"bold red","CLOSED":"bold red","DECREASE":"red","Sale":"bold red",
          "SHORT":"bold red","HOLD/LONG":"yellow","BUY (Insider)":"bold green","CALL":"cyan"}
    fc = {"STRONG_FOLLOW":"bold green","FOLLOW":"green","WATCH":"yellow",
          "CAUTION":"orange1","AVOID":"bold red"}
    fe = {"STRONG_FOLLOW":"⭐⭐⭐ STRONG","FOLLOW":"⭐⭐ FOLLOW",
          "WATCH":"👁 WATCH","CAUTION":"⚠️ CAUTION","AVOID":"❌ AVOID"}
    qc = {"STRONG_BUY":"bold green","BUY":"green","HOLD":"yellow",
          "SELL":"red","STRONG_SELL":"bold red","N/A":"dim"}

    for tr in trades:
        a_col = ac.get(tr.action, "white")
        f_col = fc.get(tr.follow, "white")
        q_col = qc.get(tr.quant_signal, "dim")
        size  = f"${tr.value_usd_m:.0f}M" if tr.value_usd_m > 0 else "—"
        q_s   = "green" if tr.quant_score>=60 else "yellow" if tr.quant_score>=45 else ("red" if tr.quant_score>0 else "dim")
        t_s   = "green" if tr.tech_score>=60  else "yellow" if tr.tech_score>=45  else ("red" if tr.tech_score>0  else "dim")
        s_s   = "green" if tr.stat_score>=60  else "yellow" if tr.stat_score>=45  else ("red" if tr.stat_score>0  else "dim")

        sig_str = "—" if tr.quant_signal in ("N/A", "") else f"[{q_col}]{tr.quant_signal}[/{q_col}]"
        t.add_row(
            tr.whale[:26], tr.ticker, tr.company[:22],
            f"[{a_col}]{tr.action}[/{a_col}]",
            size, tr.date, tr.source[:14],
            f"[{q_s}]{tr.quant_score:.0f}[/{q_s}]" if tr.quant_score>0 else "—",
            f"[{t_s}]{tr.tech_score:.0f}[/{t_s}]"  if tr.tech_score>0  else "—",
            f"[{s_s}]{tr.stat_score:.0f}[/{s_s}]"  if tr.stat_score>0  else "—",
            sig_str,
            f"[{f_col}]{fe.get(tr.follow, tr.follow)}[/{f_col}]",
        )
    return t


# Mega-caps everyone already knows — deprioritise in the "novel picks" summary
_CONSENSUS_TICKERS = {
    "AAPL","MSFT","GOOGL","GOOG","AMZN","META","TSLA","NVDA",
    "BRK.B","BRK.A","JPM","V","UNH","XOM","JNJ","WMT","PG",
}

def _novelty_score(t: "WhaleTrade") -> float:
    """Higher = more non-consensus. Penalise mega-caps, boost smaller funds."""
    base = {"STRONG_FOLLOW": 3, "FOLLOW": 2, "WATCH": 1}.get(t.follow, 0) * 10
    base += t.quant_score * 0.5
    if t.ticker.upper() in _CONSENSUS_TICKERS:
        base -= 20   # everyone knows AAPL — not novel
    # Boost picks from less-followed / newer managers
    novel_sources = {"D1 Capital","Sachem Head","Durable","Whale Rock",
                     "Situational","Scion","Duquesne","Baupost"}
    if any(ns in t.whale for ns in novel_sources):
        base += 12
    # Boost if value is small (concentrated conviction, not index-hugging)
    if 0 < t.value_usd_m < 200:
        base += 5
    return base


def render_follow_summary(all_trades: List[WhaleTrade]) -> Table:
    """
    Top follow opportunities — ranked by novelty + conviction, not just quant score.
    Filters out generic mega-cap consensus picks.
    """
    actionable = [t for t in all_trades
                  if t.follow in ("STRONG_FOLLOW","FOLLOW","WATCH")
                  and t.ticker and len(t.ticker) >= 1]

    # Per ticker: keep the trade with the best novelty score
    best: Dict[str, WhaleTrade] = {}
    for t in actionable:
        k = t.ticker.upper()
        if k not in best or _novelty_score(t) > _novelty_score(best[k]):
            best[k] = t

    ranked = sorted(best.values(), key=_novelty_score, reverse=True)[:15]

    t = Table(
        title="🎯 TOP FOLLOW OPPORTUNITIES — Novelty-ranked | Non-consensus picks first",
        box=box.HEAVY_EDGE, show_lines=True,
        header_style="bold yellow on grey11", min_width=200,
    )
    t.add_column("Rank",         justify="center", width=10)
    t.add_column("Ticker",       style="bold",     width=8)
    t.add_column("Company",                        width=22, no_wrap=True)
    t.add_column("Whale",                          width=26, no_wrap=True)
    t.add_column("Action",       justify="center", width=14)
    t.add_column("Quant/100",    justify="right",  width=10)
    t.add_column("Signal",       justify="center", width=13)
    t.add_column("Consensus?",   justify="center", width=11)
    t.add_column("Why Follow",                     width=50)

    fc = {"STRONG_FOLLOW":"bold green","FOLLOW":"green","WATCH":"yellow"}
    ac = {"BUY":"bold green","BUY (Insider)":"bold green","SELL":"red","HOLD/LONG":"yellow"}
    qc = {"STRONG_BUY":"bold green","BUY":"green","HOLD":"yellow","SELL":"red","N/A":"dim"}

    for i, tr in enumerate(ranked, 1):
        is_consensus = tr.ticker.upper() in _CONSENSUS_TICKERS
        pri_str = f"⭐⭐⭐ #{i}" if tr.follow=="STRONG_FOLLOW" else (f"⭐⭐  #{i}" if tr.follow=="FOLLOW" else f"⭐    #{i}")
        pri_col = "bold green" if i<=3 else "green"
        a_col = ac.get(tr.action, "white")
        f_col = fc.get(tr.follow, "yellow")
        q_col = qc.get(tr.quant_signal, "dim")
        q_s   = "green" if tr.quant_score>=60 else "yellow" if tr.quant_score>=45 else "red"
        sig_str = "—" if tr.quant_signal in ("N/A","") else f"[{q_col}]{tr.quant_signal}[/{q_col}]"
        consensus_str = "[dim]👥 consensus[/dim]" if is_consensus else "[bold cyan]💡 non-obvious[/bold cyan]"

        t.add_row(
            f"[{pri_col}]{pri_str}[/{pri_col}]",
            tr.ticker, tr.company[:22], tr.whale[:26],
            f"[{a_col}]{tr.action}[/{a_col}]",
            f"[{q_s}]{tr.quant_score:.0f}/100[/{q_s}]",
            sig_str,
            consensus_str,
            tr.follow_reason[:50],
        )
    return t


# ── Main Runner ────────────────────────────────────────────────────────────────

def run_whale_tracker() -> str:
    all_trades: List[WhaleTrade] = []
    summary_lines = []
    out = Console(width=220)
    return _whale_tracker_body(out, all_trades, summary_lines)


def _whale_tracker_body(out: Console, all_trades: List[WhaleTrade], summary_lines: list) -> str:
    out.rule("[bold yellow]🐋 WHALE TRACKER — Smart Money Intelligence[/bold yellow]")

    # ── Tab 1 & 2: Institutional + AI Funds (13F + ARK + Dataroma) ───────────
    out.rule("[cyan]Tab 1 & 2: Institutional + AI Funds[/cyan]")

    priority_13f = [
        # Established legends
        ("Berkshire Hathaway",    "0001067983"),
        ("Scion Asset Mgmt",      "0001649978"),
        ("Duquesne Family Office","0001536411"),
        ("Pershing Square",       "0002026053"),  # correct CIK (old was wrong entity)
        ("Viking Global",         "0001103804"),
        ("Baupost Group",         "0001060349"),
        ("Third Point LLC",       "0001040792"),
        ("Citadel Advisors",      "0001423298"),
        # AI / Tech focused
        ("Situational Awareness", "0002045724"),  # Leopold Aschenbrenner — filed 2026-05-18
        ("Coatue Management",     "0001336528"),
        ("Tiger Global",          "0001167483"),
        ("Dragoneer Investment",  "0001413754"),
        # Younger / concentrated managers
        ("D1 Capital Partners",   "0001747057"),
        ("Sachem Head Capital",   "0001582090"),
        ("Durable Capital",       "0001798849"),
        ("Whale Rock Capital",    "0001387322"),
    ]

    tab12: List[WhaleTrade] = []
    for name, cik in priority_13f:
        out.print(f"  [dim]→ Fetching 13F: {name}...[/dim]")
        tab12.extend(get_13f_trades(name, cik))
        time.sleep(0.2)

    out.print("  [dim]→ ARK daily...[/dim]")
    tab12.extend(get_ark_trades("ARKK"))

    out.print("  [dim]→ Dataroma superinvestors...[/dim]")
    tab12.extend(get_dataroma_trades())

    out.print("  [dim]→ Running quant analysis...[/dim]")
    tab12 = enrich_with_quant(tab12)
    all_trades.extend(tab12)

    # Show top 20 from institutional tab (deduplicated within this tab)
    tab12_deduped = list(deduplicate(tab12))[:20]
    if tab12_deduped:
        out.print(render_trades_table(tab12_deduped, "🏦 Institutional + AI Funds — Top Positions with Quant Signal"))
        out.print()

    # ── Tab 3: Asia Whales ────────────────────────────────────────────────────
    out.rule("[cyan]Tab 3: Asia Whales[/cyan]")
    out.print("  [dim]→ Hillhouse stopped US 13F filings in 2021. Trying historical filings...[/dim]")
    asia: List[WhaleTrade] = []
    for name, cik in [("Hillhouse Capital","0001762304"),("DST Global","0001548144"),
                      ("SoftBank Vision Fund","0001640251"),("GIC Singapore","0001641614")]:
        out.print(f"  [dim]→ {name}...[/dim]")
        trades = get_13f_trades(name, cik)
        if trades:
            asia.extend(trades)
        else:
            out.print(f"  [dim yellow]  ↳ No active 13F for {name} (foreign sovereign/private fund)[/dim yellow]")
        time.sleep(0.2)
    if asia:
        asia = enrich_with_quant(asia)
        all_trades.extend(asia)
        out.print(render_trades_table(list(deduplicate(asia))[:10], "🐉 Asia Whales — US Holdings (13F)"))
    else:
        out.print("  [yellow]Asia whales (Hillhouse/SoftBank/GIC) do not file US 13F or filings are historical only.[/yellow]")
        out.print("  [dim]→ Track via: Bloomberg/Reuters news, SoftBank quarterly reports, GIC annual report.[/dim]")
    out.print()

    # ── Tab 4: Crypto Whales ──────────────────────────────────────────────────
    out.rule("[cyan]Tab 4: Crypto Whales[/cyan]")
    crypto: List[WhaleTrade] = [
        WhaleTrade("Michael Saylor/MSTR",          "MSTR", "MicroStrategy",    "BUY",       2000, "Recent", "Public Disclosure"),
        WhaleTrade("World Liberty Fin (Trump/WLF)", "IBIT", "iShares BTC ETF",  "BUY",        500, "Recent", "Public Disclosure"),
        WhaleTrade("a16z Crypto (holdings proxy)",  "COIN", "Coinbase",          "HOLD/LONG",  800, "Recent", "Public Disclosure"),
        WhaleTrade("Pantera Capital",               "MSTR", "BTC proxy",         "BUY",        200, "Recent", "News"),
        WhaleTrade("Galaxy Digital (Novogratz)",    "MSTR", "BTC proxy",         "BUY",        150, "Recent", "News"),
    ]
    crypto = enrich_with_quant(crypto)
    all_trades.extend(crypto)
    out.print(render_trades_table(list(deduplicate(crypto)), "🐋 Crypto Whales — Public + Proxy Positions"))
    out.print()

    # ── Tab 5: Insider Buying (Finviz — verified structure) ──────────────────
    out.rule("[cyan]Tab 5: Insider Buying[/cyan]")
    out.print("  [dim]→ Fetching insider buys via Finviz...[/dim]")
    insider_raw = fetch_finviz_insiders(limit=15)
    insider: List[WhaleTrade] = []
    for row in insider_raw:
        ticker = row["ticker"]
        insider.append(WhaleTrade(
            whale=f"Insider: {row['insider']} ({row['role'][:12]})",
            ticker=ticker, company=ticker,
            action="BUY (Insider)", value_usd_m=0,
            date=row["date"], source="Finviz Insider",
        ))
    if insider:
        insider = enrich_with_quant(insider)
        all_trades.extend(insider)
        out.print(render_trades_table(list(deduplicate(insider))[:12],
                                      "⚡ Insider Buying — C-Suite & Directors (Finviz)"))
    else:
        out.print("  [dim]No insider buy data today.[/dim]")
    out.print()

    # ── Tab 6: Congressional Trades (QuiverQuant — real tickers, clean API) ──
    out.rule("[cyan]Tab 6: Political Money — STOCK Act[/cyan]")
    out.print("  [dim]→ Fetching Congressional trades via QuiverQuant...[/dim]")
    congress_raw = fetch_quiverquant_congress(limit=20)
    political: List[WhaleTrade] = []
    for row in congress_raw:
        political.append(WhaleTrade(
            whale=row["politician"], ticker=row["ticker"],
            company=row["ticker"], action=row["action"],
            value_usd_m=0, date=row["filed_date"], source="QuiverQuant",
        ))
    if political:
        political = enrich_with_quant(political)
        all_trades.extend(political)
        out.print(render_trades_table(list(deduplicate(political))[:15],
                                      "🏛️ Congressional Trades — STOCK Act (QuiverQuant)"))
    else:
        out.print("  [dim]No congressional trade data today.[/dim]")
    out.print()

    # ── Tab 7: Social & Market Intelligence ──────────────────────────────────
    out.rule("[cyan]Tab 7: Social & Market Intelligence[/cyan]")

    # 7a. StockTwits trending
    out.print("  [dim]→ StockTwits trending tickers...[/dim]")
    trending = fetch_stocktwits_trending()
    if trending:
        from rich.panel import Panel
        out.print(Panel(
            "  ".join(f"[bold cyan]{t}[/bold cyan]" for t in trending[:12]),
            title="📱 StockTwits Trending Now", border_style="cyan", expand=False,
        ))
    out.print()

    # 7b. StockTwits sentiment on current whale holdings
    whale_tickers = list({t.ticker for t in all_trades
                          if t.ticker and len(t.ticker) <= 5 and t.follow in ("STRONG_FOLLOW","FOLLOW")})[:10]
    if whale_tickers:
        out.print(f"  [dim]→ Social sentiment for whale holdings: {', '.join(whale_tickers[:6])}...[/dim]")
        sentiment = fetch_stocktwits_sentiment(whale_tickers)
        if sentiment:
            from rich.table import Table as RTable
            st = RTable(title="📊 StockTwits Sentiment — On Current Whale Holdings",
                        box=box.ROUNDED, show_lines=True, min_width=60)
            st.add_column("Ticker",    style="bold", width=8)
            st.add_column("Sentiment", justify="center", width=12)
            st.add_column("🐂 Bull%",  justify="right", width=10)
            st.add_column("Msgs",      justify="right", width=8)
            for tkr, s in sorted(sentiment.items(), key=lambda x: x[1]["bull_pct"], reverse=True):
                sc = "bold green" if s["sentiment"]=="Bullish" else ("red" if s["sentiment"]=="Bearish" else "yellow")
                bp = s["bull_pct"]
                bar = "█" * (bp // 10) + "░" * (10 - bp // 10)
                st.add_row(tkr, f"[{sc}]{s['sentiment']}[/{sc}]",
                           f"[{sc}]{bp}%[/{sc}] {bar}", str(s["count"]))
            out.print(st)
    out.print()

    # 7c. Whale news mentions (Finviz headline scan)
    out.print("  [dim]→ Scanning news for whale activity mentions...[/dim]")
    news = fetch_whale_news()
    if news:
        from rich.table import Table as NTable
        nt = NTable(title="📰 Whale News Mentions — Finviz Headlines",
                    box=box.SIMPLE, show_lines=False, min_width=160)
        nt.add_column("Whale",    width=30, no_wrap=True)
        nt.add_column("Headline", width=120)
        nt.add_column("Date",     width=10)
        for n in news:
            nt.add_row(f"[cyan]{n['whale']}[/cyan]", n["headline"], n["date"])
        out.print(nt)
    else:
        out.print("  [dim]No whale mentions in current news cycle.[/dim]")
    out.print()

    # 7d. SEC 13F filing alerts (new filings in last 24h)
    out.print("  [dim]→ SEC EDGAR 13F filing alerts...[/dim]")
    alerts = fetch_sec_13f_alerts()
    if alerts:
        from rich.table import Table as ATable
        at = ATable(title="🔔 New SEC 13F Filings — Fresh From EDGAR",
                    box=box.SIMPLE, show_lines=False, min_width=80)
        at.add_column("Filed",   width=12)
        at.add_column("Entity",  width=45)
        at.add_column("CIK",     width=12)
        for a in alerts[:10]:
            at.add_row(a["date"], f"[white]{a['name']}[/white]", a["cik"])
        out.print(at)
    out.print()

    # ── Top Follow Opportunities (deduplicated across ALL tabs) ───────────────
    out.rule("[bold yellow]🎯 BEST FOLLOW OPPORTUNITIES[/bold yellow]")
    out.print(render_follow_summary(all_trades))
    out.print()
    out.print("[dim]Scroll: output auto-paged via less -R when running in a terminal.[/dim]")

    # Build summary for AI analysis
    strong = [t for t in all_trades if t.follow == "STRONG_FOLLOW"]
    follow = [t for t in all_trades if t.follow == "FOLLOW"]
    summary_lines.append(f"WHALE TRACKER: {len(all_trades)} raw signals, {len(set(t.ticker for t in all_trades))} unique tickers")
    summary_lines.append("Strong Follow: " + ", ".join(f"{t.ticker}({t.whale[:12]})" for t in strong[:6]))
    summary_lines.append("Follow: " + ", ".join(f"{t.ticker}({t.whale[:12]})" for t in follow[:6]))

    return "\n".join(summary_lines)
