"""
Social & Market Intelligence — Whale Tracker supplementary sources

Sources (all free, no API key):
  - QuiverQuant  — Congressional trades (real tickers, clean API)
  - Finviz       — Insider buying with verified ticker structure
  - StockTwits   — Retail/social sentiment on whale holdings
  - Finviz News  — Scan headlines for whale name mentions
  - SEC EDGAR    — Real-time 13F filing alerts (RSS)
"""
import re, time, warnings
import requests
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

WEB = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
QQ  = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

# ── Congressional trades via QuiverQuant ──────────────────────────────────────

def fetch_quiverquant_congress(limit: int = 20) -> list:
    """
    Congressional stock trades from QuiverQuant free API.
    Returns list of dicts with proper tickers — much more reliable than scraping.
    """
    trades = []
    try:
        r = requests.get("https://api.quiverquant.com/beta/live/congresstrading",
                         headers=QQ, timeout=10)
        if r.status_code != 200:
            return []
        for row in r.json()[:limit * 3]:
            ticker = (row.get("Ticker") or "").strip().upper()
            if not ticker or not re.match(r'^[A-Z]{1,5}$', ticker):
                continue
            txn = row.get("Transaction", "")
            action = "BUY" if "Purchase" in txn else ("SELL" if "Sale" in txn else txn)
            if action not in ("BUY", "SELL"):
                continue
            trades.append({
                "politician": row.get("Representative", "Congress")[:28],
                "ticker":     ticker,
                "company":    ticker,
                "action":     action,
                "amount":     row.get("Range", "—"),
                "filed_date": row.get("ReportDate", "—")[:10],
                "source":     "QuiverQuant",
            })
            if len(trades) >= limit:
                break
    except Exception as e:
        print(f"  [QuiverQuant] {e}")
    return trades


# ── Insider buying via Finviz ─────────────────────────────────────────────────

def fetch_finviz_insiders(limit: int = 15) -> list:
    """
    Insider buying from Finviz screener.
    Table structure confirmed: ticker | name | role | date | Buy/Sell | price | …
    """
    trades = []
    try:
        r = requests.get(
            "https://finviz.com/insidertrading.ashx?or=-10&tv=100000&tc=1&o=-transactionValue",
            headers={**WEB, "Referer": "https://finviz.com/"},
            timeout=10,
        )
        soup = BeautifulSoup(r.text, "html.parser")
        table = soup.find("table", class_=re.compile(r"styled-table-new"))
        if not table:
            return []
        for row in table.find_all("tr")[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < 6:
                continue
            ticker = re.sub(r"[^A-Z]", "", cells[0].upper())[:5]
            txn    = cells[4]
            if not ticker or "Buy" not in txn:
                continue
            trades.append({
                "insider": cells[1][:25],
                "ticker":  ticker,
                "role":    cells[2][:20],
                "date":    cells[3],
                "action":  "BUY (Insider)",
                "price":   cells[5],
                "source":  "Finviz Insider",
            })
            if len(trades) >= limit:
                break
    except Exception as e:
        print(f"  [Finviz Insider] {e}")
    return trades


# ── StockTwits social sentiment ───────────────────────────────────────────────

def fetch_stocktwits_sentiment(tickers: list) -> dict:
    """
    Get StockTwits bullish/bearish sentiment for a list of tickers.
    Returns {ticker: {"sentiment": "Bullish"|"Bearish"|"Mixed", "bull_pct": float}}
    """
    results = {}
    for ticker in tickers[:12]:
        try:
            r = requests.get(
                f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json",
                headers=WEB, timeout=6,
            )
            if r.status_code != 200:
                continue
            msgs = r.json().get("messages", [])
            bulls = sum(1 for m in msgs if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bullish")
            bears = sum(1 for m in msgs if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bearish")
            total = bulls + bears
            if total == 0:
                results[ticker] = {"sentiment": "—", "bull_pct": 0, "count": len(msgs)}
            else:
                pct = round(bulls / total * 100)
                sent = "Bullish" if pct >= 60 else ("Bearish" if pct <= 40 else "Mixed")
                results[ticker] = {"sentiment": sent, "bull_pct": pct, "count": len(msgs)}
            time.sleep(0.1)
        except Exception:
            continue
    return results


def fetch_stocktwits_trending() -> list:
    """Top trending tickers on StockTwits right now."""
    try:
        r = requests.get("https://api.stocktwits.com/api/2/trending/symbols.json",
                         headers=WEB, timeout=8)
        if r.status_code == 200:
            return [s["symbol"] for s in r.json().get("symbols", [])
                    if re.match(r'^[A-Z]{1,5}$', s.get("symbol", ""))]
    except Exception as e:
        print(f"  [StockTwits trending] {e}")
    return []


# ── Finviz news — scan for whale name mentions ────────────────────────────────

WHALE_NAMES = [
    ("Ackman",        "Bill Ackman / Pershing Square"),
    ("Saylor",        "Michael Saylor / MSTR"),
    ("Druckenmiller", "Stanley Druckenmiller"),
    ("Berkshire",     "Warren Buffett / Berkshire"),
    ("Burry",         "Michael Burry / Scion"),
    ("Loeb",          "Dan Loeb / Third Point"),
    ("Klarman",       "Seth Klarman / Baupost"),
    ("Sundheim",      "Dan Sundheim / D1 Capital"),
    ("Aschenbrenner", "Leopold / Situational Awareness"),
    ("chamath",       "Chamath Palihapitiya"),
    ("Tepper",        "David Tepper"),
    ("Einhorn",       "David Einhorn / Greenlight"),
    ("Cooperman",     "Leon Cooperman / Omega"),
    ("Viking",        "Viking Global"),
    ("Elliott",       "Elliott Management"),
]

def fetch_whale_news() -> list:
    """
    Scrape Finviz news headlines for whale name mentions.
    Returns list of {whale, headline, url, date}.
    """
    mentions = []
    try:
        r = requests.get("https://finviz.com/news.ashx",
                         headers=WEB, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for row in soup.select("table.fullview-news-outer tr, tr"):
            a = row.find("a")
            if not a:
                continue
            headline = a.get_text(strip=True)
            url      = a.get("href", "")
            date_td  = row.find("td", class_="news-date-cell") or row.find("td")
            date_str = date_td.get_text(strip=True) if date_td else ""
            lower    = headline.lower()
            for keyword, label in WHALE_NAMES:
                if keyword.lower() in lower:
                    mentions.append({
                        "whale":    label,
                        "headline": headline[:120],
                        "url":      url,
                        "date":     date_str[:12],
                    })
                    break
    except Exception as e:
        print(f"  [Finviz news] {e}")

    # Deduplicate by headline
    seen = set()
    deduped = []
    for m in mentions:
        if m["headline"] not in seen:
            seen.add(m["headline"])
            deduped.append(m)
    return deduped[:15]


# ── SEC EDGAR 13F new filing alerts ──────────────────────────────────────────

def fetch_sec_13f_alerts() -> list:
    """
    Pull latest 13F-HR filings from SEC EDGAR RSS.
    Good for catching brand-new filings before they're aggregated elsewhere.
    """
    filings = []
    try:
        r = requests.get(
            "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent"
            "&type=13F-HR&dateb=&owner=include&count=20&search_text=&output=atom",
            headers={"User-Agent": "SignalForge research@signalforge.io"},
            timeout=10,
        )
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")
        for entry in soup.find_all("entry")[:20]:
            company = entry.find("company-name")
            date    = entry.find("filing-date")
            link    = entry.find("filing-href")
            cik_tag = entry.find("cik")
            if company and date:
                filings.append({
                    "name":    company.get_text(strip=True)[:40],
                    "date":    date.get_text(strip=True)[:10],
                    "cik":     cik_tag.get_text(strip=True) if cik_tag else "",
                    "url":     link.get_text(strip=True) if link else "",
                })
    except Exception as e:
        print(f"  [SEC 13F RSS] {e}")
    return filings
