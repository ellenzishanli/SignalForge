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

from whales.sec_13f import fetch_13f, fetch_13f_with_changes, fetch_ark_holdings, fetch_capitol_trades
from whales.social_signals import (
    fetch_quiverquant_congress, fetch_finviz_insiders,
    fetch_stocktwits_sentiment, fetch_stocktwits_trending,
    fetch_whale_news, fetch_sec_13f_alerts,
)
from config.whales import ALL_WHALES
from stocks.parallel import parallel_fetch

console = Console(width=280)
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


_COMPANY_NAME_CACHE: Dict[str, str] = {}

def _company_name(ticker: str) -> str:
    """Return human-readable company name for a ticker (cached)."""
    if not ticker or len(ticker) > 5:
        return ticker
    if ticker in _COMPANY_NAME_CACHE:
        return _COMPANY_NAME_CACHE[ticker]
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        name = info.get("shortName") or info.get("longName") or ticker
        _COMPANY_NAME_CACHE[ticker] = name[:28]
        return name[:28]
    except Exception:
        _COMPANY_NAME_CACHE[ticker] = ticker
        return ticker


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
    """Fetch 13F with QoQ change detection. Returns one WhaleTrade per holding."""
    filing = fetch_13f_with_changes(entity_name, cik, top_n=60)
    if not filing or not filing.holdings:
        return []
    trades = []
    for h in filing.holdings:
        if not h.name:
            continue
        # Decode change annotation from put_call field
        change = "HOLD"
        put_call_raw = h.put_call or ""
        if put_call_raw.startswith("chg:"):
            change = put_call_raw[4:]
            put_call_raw = ""

        if put_call_raw == "Put":
            action = "SHORT"
        elif put_call_raw == "Call":
            action = "CALL"
        elif change == "NEW":
            action = "NEW BUY"
        elif change == "INCREASED":
            action = "INCREASED"
        elif change == "DECREASED":
            action = "DECREASED"
        else:
            action = "HOLD/LONG"

        ticker = h.ticker or ""
        # Skip holdings with no ticker AND no recognisable name (noise rows)
        if not ticker and len(h.name) < 3:
            continue

        trades.append(WhaleTrade(
            whale=entity_name, ticker=ticker, company=h.name[:32],
            action=action, value_usd_m=h.value_usd / 1e6,
            date=f"Q{filing.period[:7]}", source="SEC 13F",
            quant_signal=change,   # temporarily store change here for display
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


# ── Consolidated holdings table ───────────────────────────────────────────────

def render_consolidated_table(trades: List[WhaleTrade], title: str,
                               show_new_only: bool = False) -> Table:
    """
    Groups holdings by ticker. One row per stock/ETF.
    Columns: Ticker | Company | # Funds | Who holds it (fund: % allocation) |
             Total $M | Change | Quant | Signal | Follow
    """
    from collections import defaultdict

    # Group by ticker (skip blank tickers)
    by_ticker: Dict[str, List[WhaleTrade]] = defaultdict(list)
    for t in trades:
        if t.ticker and len(t.ticker) >= 1:
            by_ticker[t.ticker.upper()].append(t)

    # Filter to new/increased only if requested
    CHANGE_PRIORITY = {"NEW BUY": 4, "INCREASED": 3, "HOLD/LONG": 2,
                       "DECREASED": 1, "SHORT": 0, "CALL": 2}
    rows = []
    for ticker, ts in by_ticker.items():
        if show_new_only:
            has_new = any(t.action in ("NEW BUY","INCREASED") for t in ts)
            if not has_new:
                continue
        best = max(ts, key=lambda t: t.quant_score)
        total_val = sum(t.value_usd_m for t in ts)
        fund_parts = []
        for t in sorted(ts, key=lambda x: x.value_usd_m, reverse=True)[:2]:
            name_s = t.whale[:12].rstrip()
            sz = (f"${t.value_usd_m/1000:.1f}B" if t.value_usd_m >= 1000
                  else f"${t.value_usd_m:.0f}M" if t.value_usd_m > 0 else "?")
            fund_parts.append(f"{name_s}({sz})")
        top_change = max(ts, key=lambda t: CHANGE_PRIORITY.get(t.action, 0)).action
        rows.append((ticker, best, ts, total_val, fund_parts, top_change))

    # Sort: new/increased first, then by total value
    rows.sort(key=lambda r: (
        CHANGE_PRIORITY.get(r[5], 0),
        r[3]
    ), reverse=True)

    tbl = Table(title=title, box=box.ROUNDED, show_lines=True,
                header_style="bold white on dark_blue", min_width=140)
    tbl.add_column("Ticker",   width=7,  style="bold")
    tbl.add_column("Company",  width=24, no_wrap=True)
    tbl.add_column("Holders",  width=46, no_wrap=True)
    tbl.add_column("Total $M", width=10, justify="right")
    tbl.add_column("Change",   width=12, justify="center")
    tbl.add_column("Quant",    width=7,  justify="right")
    tbl.add_column("Signal",   width=12, justify="center")
    tbl.add_column("Follow",   width=14, justify="center")

    CHANGE_COLOR = {"NEW BUY":"bold green","INCREASED":"green",
                    "DECREASED":"red","HOLD/LONG":"dim","SHORT":"bold red","CALL":"cyan"}
    FOLLOW_EMOJI = {"STRONG_FOLLOW":"⭐⭐⭐","FOLLOW":"⭐⭐","WATCH":"👁",
                    "CAUTION":"⚠️","AVOID":"❌"}
    FOLLOW_COLOR = {"STRONG_FOLLOW":"bold green","FOLLOW":"green",
                    "WATCH":"yellow","CAUTION":"orange1","AVOID":"bold red"}
    QC = {"STRONG_BUY":"bold green","BUY":"green","HOLD":"yellow","SELL":"red"}

    for ticker, best, ts, total_val, fund_parts, top_change in rows[:60]:
        q_s = "green" if best.quant_score>=60 else ("yellow" if best.quant_score>=45 else "red")
        q_col = QC.get(best.quant_signal, "dim")
        f_col = FOLLOW_COLOR.get(best.follow, "white")
        c_col = CHANGE_COLOR.get(top_change, "dim")
        sig_str = "—" if best.quant_signal in ("N/A","","HOLD","NEW BUY","INCREASED",
                                                "DECREASED","CLOSED") else f"[{q_col}]{best.quant_signal}[/{q_col}]"
        n_extra = len(ts) - 2
        holders_str = "  ".join(fund_parts) + (f"  +{n_extra}" if n_extra > 0 else "")
        tbl.add_row(
            ticker,
            best.company[:24],
            holders_str,
            f"${total_val:.0f}M" if total_val > 0 else "—",
            f"[{c_col}]{top_change}[/{c_col}]",
            f"[{q_s}]{best.quant_score:.0f}[/{q_s}]" if best.quant_score > 0 else "—",
            sig_str,
            f"[{f_col}]{FOLLOW_EMOJI.get(best.follow,'')} {best.follow}[/{f_col}]",
        )
    return tbl


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
    import os
    os.environ.setdefault("LESS", "-RS")
    all_trades: List[WhaleTrade] = []
    summary_lines = []
    out = Console(width=280)
    with out.pager(styles=True):
        _whale_tracker_body(out, all_trades, summary_lines)
    return "\n".join(summary_lines)


def _whale_tracker_body(out: Console, all_trades: List[WhaleTrade], summary_lines: list) -> None:
    out.rule("[bold yellow]🐋 WHALE TRACKER — Smart Money Intelligence[/bold yellow]")

    # ── Tab 1 & 2: Institutional + AI Funds (13F + ARK + Dataroma) ───────────
    out.rule("[cyan]Tab 1 & 2: Institutional + AI Funds[/cyan]")

    priority_13f = [
        # ── Value investors & activists (highest conviction, buy-and-hold) ──────
        ("Berkshire Hathaway",    "0001067983"),
        ("Baupost Group",         "0001060349"),
        ("Pershing Square",       "0002026053"),
        ("Scion Asset Mgmt",      "0001649978"),
        ("Third Point LLC",       "0001040792"),
        ("Elliott Management",    "0001048268"),
        ("Sachem Head Capital",   "0001582090"),
        # ── Global macro / concentrated growth ───────────────────────────────────
        ("Duquesne Family Office","0001536411"),
        ("Viking Global",         "0001103804"),
        ("D1 Capital Partners",   "0001747057"),
        ("Durable Capital",       "0001798849"),
        ("Whale Rock Capital",    "0001387322"),
        # ── AI / Tech focused ────────────────────────────────────────────────────
        ("Situational Awareness", "0002045724"),  # Leopold — latest 13F 2026-05-18
        ("Coatue Management",     "0001336528"),
        ("Tiger Global",          "0001167483"),
        ("Dragoneer Investment",  "0001413754"),
        # ── Quant giants (13F = long equity book only, not full strategy) ────────
        ("Bridgewater Associates","0001350694"),
        ("Renaissance Tech",      "0001037389"),
        ("Citadel Advisors",      "0001423053"),  # correct CIK (was 0001423298 = wrong entity)
        ("Point72 Asset Mgmt",    "0001603466"),
        ("D. E. Shaw & Co.",      "0001009207"),
        ("Two Sigma Advisers",    "0001478735"),
        ("WorldQuant Millennium", "0001745981"),
    ]

    # Fetch all funds' 13F filings concurrently. A global 8 req/s limiter inside
    # sec_13f keeps us within SEC EDGAR's 10 req/s fair-access ceiling regardless
    # of how many fund threads are in flight — so this is fast AND compliant.
    out.print(f"  [dim]→ Fetching {len(priority_13f)} funds' 13F filings in parallel (SEC rate-limited)...[/dim]")
    tab12: List[WhaleTrade] = []
    fund_trade_lists = parallel_fetch(
        priority_13f,
        lambda job: get_13f_trades(job[0], job[1]),
        max_workers=6,
    )
    for trades in fund_trade_lists:
        tab12.extend(trades)

    out.print("  [dim]→ ARK daily...[/dim]")
    tab12.extend(get_ark_trades("ARKK"))

    out.print("  [dim]→ Running quant analysis...[/dim]")
    tab12 = enrich_with_quant(tab12)
    all_trades.extend(tab12)

    # ── Consolidated by ticker (no duplicates) ──────────────────────────────
    out.print(render_consolidated_table(
        tab12,
        "🏦 All Whale Holdings — Consolidated by Stock (60 top positions per fund, QoQ change)",
        show_new_only=False,
    ))
    out.print()

    # ── New & Increased positions this quarter ──────────────────────────────
    new_trades = [t for t in tab12 if t.action in ("NEW BUY", "INCREASED")]
    if new_trades:
        out.print(render_consolidated_table(
            new_trades,
            "🆕 NEW & INCREASED Positions This Quarter — Strongest Buy Signal",
            show_new_only=True,
        ))
    out.print()

    # ── Tab 3: Crypto Whales ─────────────────────────────────────────────────
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
            ticker=ticker, company=_company_name(ticker),
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
            company=_company_name(row["ticker"]), action=row["action"],
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
    out.print("[dim]← → scroll horizontally  |  ↑ ↓ scroll vertically  |  q to exit[/dim]")

    # Build summary for AI analysis
    strong = [t for t in all_trades if t.follow == "STRONG_FOLLOW"]
    follow = [t for t in all_trades if t.follow == "FOLLOW"]
    summary_lines.append(f"WHALE TRACKER: {len(all_trades)} raw signals, {len(set(t.ticker for t in all_trades))} unique tickers")
    summary_lines.append("Strong Follow: " + ", ".join(f"{t.ticker}({t.whale[:12]})" for t in strong[:6]))
    summary_lines.append("Follow: " + ", ".join(f"{t.ticker}({t.whale[:12]})" for t in follow[:6]))
