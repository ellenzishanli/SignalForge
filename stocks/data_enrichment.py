"""
Data Enrichment — supplements Yahoo Finance with free alternative sources.

Sources:
  1. Finviz (finviz.com)       — short interest, insider activity, analyst count, news sentiment
  2. Stockanalysis.com         — revenue estimates, EPS estimates, analyst consensus
  3. SEC EDGAR                 — recent 10-K/10-Q/8-K filings, revenue from filings
  4. Macrotrends               — historical revenue / margin trends
  5. OpenBB / FRED             — macro context

All sources are publicly accessible and free.
"""
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import re
import time


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class EnrichedData:
    """Additional data points from non-Yahoo sources."""
    ticker: str
    # Finviz
    short_float_pct: Optional[float] = None     # % of float sold short
    insider_own_pct: Optional[float] = None     # % of shares owned by insiders
    inst_own_pct: Optional[float] = None        # % owned by institutions
    analyst_count: Optional[int] = None         # number of analysts covering
    avg_volume_10d: Optional[float] = None
    relative_volume: Optional[float] = None     # today vol / avg vol
    earnings_date: Optional[str] = None
    news_headlines: List[str] = field(default_factory=list)
    # Stockanalysis
    revenue_ttm_m: Optional[float] = None       # TTM revenue in $M
    revenue_next_yr_est_m: Optional[float] = None
    eps_ttm: Optional[float] = None
    eps_next_yr_est: Optional[float] = None
    analyst_buy_count: Optional[int] = None
    analyst_hold_count: Optional[int] = None
    analyst_sell_count: Optional[int] = None
    # SEC EDGAR
    latest_filing_type: Optional[str] = None    # 10-K, 10-Q, 8-K
    latest_filing_date: Optional[str] = None
    # Computed
    buy_pct: Optional[float] = None             # % of analysts with BUY rating
    error_sources: List[str] = field(default_factory=list)


def fetch_finviz(ticker: str) -> Dict:
    """Scrape Finviz for short interest, insider/inst ownership, analyst data."""
    url = f"https://finviz.com/quote.ashx?t={ticker}"
    result = {}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return result

        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(" ")

        # Regex-based extraction (more reliable than CSS selectors for Finviz)
        patterns = {
            "short_float_pct":  r"Short Float\s*([\d.]+)%",
            "insider_own_pct":  r"Insider Own\s*([\d.]+)%",
            "inst_own_pct":     r"Inst Own\s*([\d.]+)%",
            "relative_volume":  r"Rel Volume\s*([\d.]+)",
            "target_price":     r"Target Price\s*([\d.]+)",
            "recom":            r"Recom\s*([\d.]+)",
            "beta":             r"Beta\s*([\d.]+)",
            "rsi14":            r"RSI \(14\)\s*([\d.]+)",
        }

        def parse_pct(s):
            try: return float(s.replace("%","").replace(",","").strip())
            except: return None

        for key, pattern in patterns.items():
            m = re.search(pattern, text)
            if m:
                try:
                    result[key] = float(m.group(1))
                except ValueError:
                    pass

        # Earnings date
        e = re.search(r"Earnings\s+([A-Za-z]{3}\s+\d{1,2}\s+[AP]MC)", text)
        result["earnings_date"] = e.group(1) if e else ""

        # Average volume
        av = re.search(r"Avg Volume\s*([\d.]+[KMB]?)", text)
        if av:
            s = av.group(1)
            mult = {"K": 1e3, "M": 1e6, "B": 1e9}.get(s[-1], 1)
            try:
                result["avg_volume_10d"] = float(s[:-1] if s[-1] in "KMB" else s) * mult
            except ValueError:
                pass

        # News headlines
        news = []
        for row in soup.select("table#news-table tr")[:5]:
            link = row.select_one("a")
            if link:
                news.append(link.get_text(strip=True)[:100])
        result["news_headlines"] = news

        # Analyst ratings from Finviz recommendations table
        buy_c = hold_c = sell_c = 0
        for row in soup.select("table.fullview-ratings-outer tr"):
            cells = [td.get_text(strip=True) for td in row.select("td")]
            if len(cells) >= 3:
                action_text = " ".join(cells).lower()
                if "buy" in action_text or "outperform" in action_text or "overweight" in action_text:
                    buy_c += 1
                elif "hold" in action_text or "neutral" in action_text or "market perform" in action_text:
                    hold_c += 1
                elif "sell" in action_text or "underperform" in action_text or "underweight" in action_text:
                    sell_c += 1
        if buy_c + hold_c + sell_c > 0:
            result["analyst_buy_count"]  = buy_c
            result["analyst_hold_count"] = hold_c
            result["analyst_sell_count"] = sell_c

    except Exception as e:
        result["error"] = str(e)
    return result


def fetch_stockanalysis(ticker: str) -> Dict:
    """Scrape stockanalysis.com for revenue estimates and analyst consensus."""
    url = f"https://stockanalysis.com/stocks/{ticker.lower()}/"
    result = {}
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return result
        soup = BeautifulSoup(resp.text, "html.parser")

        # Analyst ratings table
        for table in soup.select("table"):
            headers_row = [th.get_text(strip=True) for th in table.select("th")]
            if "Buy" in headers_row or "Strong Buy" in headers_row:
                rows = table.select("tr")
                for row in rows:
                    cells = [td.get_text(strip=True) for td in row.select("td")]
                    if cells and len(cells) >= 2:
                        label = cells[0].lower()
                        try:
                            val = int(cells[1])
                            if "buy" in label:
                                result["analyst_buy_count"] = result.get("analyst_buy_count", 0) + val
                            elif "hold" in label or "neutral" in label:
                                result["analyst_hold_count"] = result.get("analyst_hold_count", 0) + val
                            elif "sell" in label:
                                result["analyst_sell_count"] = result.get("analyst_sell_count", 0) + val
                        except ValueError:
                            pass

        # Revenue / EPS from key stats
        text = soup.get_text()
        rev_match = re.search(r'Revenue[:\s]+\$?([\d,.]+)\s*(B|M|K)?', text)
        if rev_match:
            val = float(rev_match.group(1).replace(",", ""))
            mult = {"B": 1000, "M": 1, "K": 0.001}.get(rev_match.group(2), 1)
            result["revenue_ttm_m"] = val * mult

    except Exception as e:
        result["error_sa"] = str(e)
    return result


def fetch_sec_latest_filing(ticker: str) -> Dict:
    """Get latest SEC filing type and date from EDGAR."""
    result = {}
    try:
        # EDGAR full-text search API (free)
        url = f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt=2024-01-01&forms=10-K,10-Q,8-K"
        resp = requests.get(url, headers={"User-Agent": "FrontierTechRadar research@example.com"}, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])
            if hits:
                latest = hits[0].get("_source", {})
                result["latest_filing_type"] = latest.get("form_type", "")
                result["latest_filing_date"] = latest.get("file_date", "")
    except Exception:
        pass
    return result


def enrich_ticker(ticker: str, delay: float = 0.3) -> EnrichedData:
    """Fetch enrichment data from all sources for one ticker."""
    ed = EnrichedData(ticker=ticker)

    fv = fetch_finviz(ticker)
    ed.short_float_pct  = fv.get("short_float_pct")
    ed.insider_own_pct  = fv.get("insider_own_pct")
    ed.inst_own_pct     = fv.get("inst_own_pct")
    ed.avg_volume_10d   = fv.get("avg_volume_10d")
    ed.relative_volume  = fv.get("relative_volume")
    ed.earnings_date    = fv.get("earnings_date")
    ed.news_headlines   = fv.get("news_headlines", [])

    time.sleep(delay)  # polite scraping rate

    sa = fetch_stockanalysis(ticker)
    ed.revenue_ttm_m        = sa.get("revenue_ttm_m")
    ed.analyst_buy_count    = sa.get("analyst_buy_count")
    ed.analyst_hold_count   = sa.get("analyst_hold_count")
    ed.analyst_sell_count   = sa.get("analyst_sell_count")

    total = (ed.analyst_buy_count or 0) + (ed.analyst_hold_count or 0) + (ed.analyst_sell_count or 0)
    if total > 0:
        ed.buy_pct = round((ed.analyst_buy_count or 0) / total * 100, 1)

    time.sleep(delay)

    sec = fetch_sec_latest_filing(ticker)
    ed.latest_filing_type = sec.get("latest_filing_type")
    ed.latest_filing_date = sec.get("latest_filing_date")

    return ed


def format_enrichment(ed: EnrichedData) -> str:
    """Format enriched data into a string for AI context."""
    parts = []
    if ed.short_float_pct is not None:
        flag = " ⚠️HIGH SHORT" if ed.short_float_pct > 20 else ""
        parts.append(f"Short Interest: {ed.short_float_pct:.1f}%{flag}")
    if ed.insider_own_pct is not None:
        parts.append(f"Insider Ownership: {ed.insider_own_pct:.1f}%")
    if ed.inst_own_pct is not None:
        parts.append(f"Institutional Ownership: {ed.inst_own_pct:.1f}%")
    if ed.buy_pct is not None:
        b = ed.analyst_buy_count or 0
        h = ed.analyst_hold_count or 0
        s = ed.analyst_sell_count or 0
        parts.append(f"Analyst Ratings: {b}B/{h}H/{s}S ({ed.buy_pct:.0f}% BUY)")
    if ed.revenue_ttm_m:
        parts.append(f"Revenue TTM: ${ed.revenue_ttm_m:.0f}M")
    if ed.earnings_date:
        parts.append(f"Earnings: {ed.earnings_date}")
    if ed.latest_filing_type:
        parts.append(f"Latest SEC filing: {ed.latest_filing_type} ({ed.latest_filing_date})")
    if ed.news_headlines:
        parts.append("Recent news: " + " | ".join(ed.news_headlines[:2]))
    return " | ".join(parts) if parts else "No enrichment data available"
