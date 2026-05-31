"""
SEC EDGAR 13F Parser — Institutional Holdings Tracker

13F filings are mandatory for institutions managing >$100M in US equities.
Filed quarterly (45 days after quarter end). Completely free and public.

API: https://data.sec.gov/submissions/CIK{cik}.json (no key needed)
     https://data.sec.gov/api/xbrl/frames/ (structured data)
"""
import requests
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime
import time


HEADERS = {"User-Agent": "SignalForge research@signalforge.io"}  # SEC requires User-Agent


@dataclass
class Holding:
    """Single stock position from a 13F filing."""
    name: str               # company name
    ticker: str             # ticker symbol (not always in 13F — we map it)
    cusip: str              # CUSIP identifier
    shares: int             # number of shares
    value_usd: int          # market value in USD (thousands in raw data)
    put_call: str           # "" | "Put" | "Call"
    change_type: str        # "NEW" | "INCREASED" | "DECREASED" | "UNCHANGED" | "CLOSED"
    change_pct: float       # % change from prior quarter


@dataclass
class Filing13F:
    """One 13F filing — one quarter of holdings for one institution."""
    entity_name: str
    cik: str
    period: str             # e.g. "2026-03-31"
    filed_date: str
    total_value_usd: int    # total portfolio value in USD
    holdings: List[Holding] = field(default_factory=list)
    top_new: List[Holding] = field(default_factory=list)      # new positions this quarter
    top_added: List[Holding] = field(default_factory=list)    # increased positions
    top_cut: List[Holding] = field(default_factory=list)      # decreased positions
    top_closed: List[Holding] = field(default_factory=list)   # fully exited


def _get_latest_13f_accession(cik: str) -> Optional[str]:
    """Get the accession number of the most recent 13F filing for a CIK."""
    cik_padded = cik.zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        accessions = filings.get("accessionNumber", [])
        dates = filings.get("filingDate", [])
        periods = filings.get("reportDate", [])

        # Find most recent 13F-HR
        for i, form in enumerate(forms):
            if form in ("13F-HR", "13F-HR/A"):
                return {
                    "accession": accessions[i].replace("-", ""),
                    "filed_date": dates[i],
                    "period": periods[i],
                    "accession_raw": accessions[i],
                }
    except Exception as e:
        print(f"[13F] Error fetching submissions for CIK {cik}: {e}")
    return None


def _parse_13f_xml(cik: str, accession: str) -> List[Dict]:
    """Download and parse the 13F information table XML."""
    cik_padded = cik.zfill(10)
    # Try the primary document
    base_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/"

    # First get the filing index to find the correct XML file
    index_url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    holdings = []

    try:
        # Direct approach: fetch the infotable XML
        xml_url = base_url + "infotable.xml"
        r = requests.get(xml_url, headers=HEADERS, timeout=15)

        if r.status_code != 200:
            # Try alternative naming
            xml_url = base_url + "form13fInfoTable.xml"
            r = requests.get(xml_url, headers=HEADERS, timeout=15)

        if r.status_code == 200:
            holdings = _parse_xml_holdings(r.text)
    except Exception as e:
        print(f"[13F] Error fetching XML for {cik}: {e}")

    return holdings


def _parse_xml_holdings(xml_text: str) -> List[Dict]:
    """Parse 13F XML info table into list of holding dicts."""
    from xml.etree import ElementTree as ET
    holdings = []

    try:
        # Handle namespace
        xml_text = xml_text.replace(' xmlns="', ' xmlns_ignore="')
        root = ET.fromstring(xml_text)

        for info in root.iter("infoTable"):
            def get(tag):
                el = info.find(tag)
                return el.text.strip() if el is not None and el.text else ""

            name     = get("nameOfIssuer")
            cusip    = get("cusip")
            value    = get("value")       # in thousands
            shares   = get("sshPrnamt")   # shares or principal amount
            put_call = get("putCall")

            holdings.append({
                "name":     name,
                "cusip":    cusip,
                "value":    int(value.replace(",", "")) * 1000 if value else 0,
                "shares":   int(shares.replace(",", "")) if shares else 0,
                "put_call": put_call,
            })
    except Exception as e:
        print(f"[13F] XML parse error: {e}")

    return holdings


# CUSIP → Ticker mapping for common stocks (supplemented by lookup)
CUSIP_TO_TICKER = {
    "037833100": "AAPL", "023135106": "AMZN", "02079K305": "GOOGL",
    "594918104": "MSFT", "67066G104": "NVDA", "88160R101": "TSLA",
    "30303M102": "META", "46090E103": "SPOT", "079679102": "AMD",
    "45866F104": "INTC", "126650100": "CVX", "172967424": "C",
    "38141G104": "GS",   "46625H100": "JPM", "172967101": "BAC",
    "842162109": "SO",   "58933Y105": "NEE", "025816109": "AXP",
    "097023105": "BRK",  "38259P508": "GOOG","000000000": "",
}


def fetch_13f(entity_name: str, cik: str) -> Optional[Filing13F]:
    """Fetch and parse the most recent 13F for an entity."""
    if not cik:
        return None

    info = _get_latest_13f_accession(cik)
    if not info:
        return None

    time.sleep(0.2)  # polite rate limiting for SEC API
    raw_holdings = _parse_13f_xml(cik, info["accession"])

    if not raw_holdings:
        # Fallback: return metadata only without holdings
        return Filing13F(
            entity_name=entity_name, cik=cik,
            period=info["period"], filed_date=info["filed_date"],
            total_value_usd=0, holdings=[],
        )

    # Sort by value and convert
    raw_holdings.sort(key=lambda x: x["value"], reverse=True)
    total_value = sum(h["value"] for h in raw_holdings)

    holdings = []
    for h in raw_holdings:
        ticker = CUSIP_TO_TICKER.get(h["cusip"], "")
        holdings.append(Holding(
            name=h["name"], ticker=ticker, cusip=h["cusip"],
            shares=h["shares"], value_usd=h["value"],
            put_call=h.get("put_call", ""),
            change_type="UNKNOWN", change_pct=0.0,
        ))

    return Filing13F(
        entity_name=entity_name, cik=cik,
        period=info["period"], filed_date=info["filed_date"],
        total_value_usd=total_value, holdings=holdings[:50],  # top 50
    )


def fetch_ark_holdings(fund: str = "ARKK") -> List[Dict]:
    """ARK publishes daily holdings CSV — real-time, no 13F lag."""
    from config.whales import ARK_FUNDS
    url = ARK_FUNDS.get(fund)
    if not url:
        return []
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        lines = r.text.strip().split("\n")
        holdings = []
        for line in lines[1:]:  # skip header
            parts = line.split(",")
            if len(parts) >= 6:
                try:
                    holdings.append({
                        "fund": fund,
                        "ticker": parts[3].strip().replace('"', ''),
                        "name": parts[2].strip().replace('"', ''),
                        "shares": int(parts[5].replace('"', '').replace(',', '')) if parts[5].strip() else 0,
                        "weight_pct": float(parts[7].replace('"', '').replace('%', '')) if len(parts) > 7 else 0,
                    })
                except (ValueError, IndexError):
                    continue
        return sorted(holdings, key=lambda x: x.get("weight_pct", 0), reverse=True)[:20]
    except Exception as e:
        print(f"[ARK] Error fetching {fund}: {e}")
        return []


def fetch_capitol_trades(limit: int = 20) -> List[Dict]:
    """Scrape recent politician stock trades from capitoltrades.com."""
    url = "https://www.capitoltrades.com/trades?per_page=20"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }
    trades = []
    try:
        from bs4 import BeautifulSoup
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        # Capitol Trades uses data attributes and specific class names
        for row in soup.select("tr.q-tr")[:limit]:
            try:
                politician = row.select_one("[data-label='Politician']")
                ticker_el  = row.select_one("[data-label='Ticker'], .q-field--ticker, td:nth-child(3)")
                action_el  = row.select_one("[data-label='Type'], td:nth-child(5)")
                amount_el  = row.select_one("[data-label='Amount'], td:nth-child(6)")
                date_el    = row.select_one("[data-label='Filed'], td:nth-child(7)")

                ticker = ticker_el.get_text(strip=True) if ticker_el else ""
                # Only keep valid tickers (1-5 uppercase letters)
                import re
                ticker = re.sub(r'[^A-Z]', '', ticker.upper())[:5]
                if not ticker or len(ticker) < 1:
                    continue

                trades.append({
                    "politician": politician.get_text(strip=True)[:30] if politician else "—",
                    "ticker":     ticker,
                    "action":     action_el.get_text(strip=True) if action_el else "—",
                    "amount":     amount_el.get_text(strip=True) if amount_el else "—",
                    "filed_date": date_el.get_text(strip=True) if date_el else "—",
                })
            except Exception:
                continue

        # Fallback: try senate stock watcher API
        if not trades:
            api_url = "https://senate-stock-watcher-data.s3-us-gov-west-1.amazonaws.com/aggregate/all_transactions_for_senator.json"
            rj = requests.get(api_url, timeout=8)
            data = rj.json()
            for senator_data in list(data.values())[:5]:
                for tx in senator_data[:4]:
                    ticker = tx.get("ticker", "").strip().upper()
                    if ticker and ticker != "--":
                        trades.append({
                            "politician": tx.get("senator", "Senator"),
                            "ticker":     ticker,
                            "action":     tx.get("type", "—"),
                            "amount":     tx.get("amount", "—"),
                            "filed_date": tx.get("transaction_date", "—"),
                        })

    except Exception as e:
        print(f"[Capitol] Error: {e}")
    return trades[:limit]
