"""
SEC EDGAR 13F Parser — Institutional Holdings Tracker
Uses the correct EDGAR API flow: submissions → accession → filing index → XML
"""
import requests, time, re, json
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "SignalForge research@signalforge.io",
    "Accept-Encoding": "gzip, deflate",
}
WEB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


@dataclass
class Holding:
    name: str
    ticker: str
    cusip: str
    shares: int
    value_usd: int        # in dollars (already *1000 from raw data)
    put_call: str         # "" | "Put" | "Call"


@dataclass
class Filing13F:
    entity_name: str
    cik: str
    period: str
    filed_date: str
    total_value_usd: int
    holdings: List[Holding] = field(default_factory=list)


# ── Step 1: Get latest 13F accession number ───────────────────────────────────

def _get_latest_13f_info(cik: str) -> Optional[dict]:
    cik_padded = cik.lstrip("0").zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        data = r.json()
        filings = data.get("filings", {}).get("recent", {})
        forms  = filings.get("form", [])
        accs   = filings.get("accessionNumber", [])
        dates  = filings.get("filingDate", [])
        periods= filings.get("reportDate", [])
        for i, form in enumerate(forms):
            if form in ("13F-HR", "13F-HR/A"):
                return {
                    "accession_raw": accs[i],
                    "accession":     accs[i].replace("-", ""),
                    "filed_date":    dates[i],
                    "period":        periods[i],
                    "cik_int":       str(int(cik.lstrip("0") or "0")),
                }
    except Exception as e:
        print(f"  [13F] submissions error for CIK {cik}: {e}")
    return None


# ── Step 2: Get filing index → find correct XML filename ─────────────────────

def _get_xml_filename(cik_int: str, accession: str) -> Optional[str]:
    """Look at the filing index page to find the infotable XML file."""
    index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{accession}-index.htm"
    try:
        r = requests.get(index_url, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            # try json index
            idx_url2 = f"https://data.sec.gov/submissions/CIK{cik_int.zfill(10)}.json"
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        for link in soup.find_all("a", href=True):
            href = link["href"].lower()
            if any(x in href for x in ["infotable", "form13f", "informationtable"]) and href.endswith(".xml"):
                return link["href"].split("/")[-1]
    except Exception:
        pass
    # Common fallback names
    return None


def _try_xml_names(cik_int: str, accession: str) -> Optional[str]:
    """
    Find the correct XML file in a 13F filing.
    Strategy: fetch the directory index, collect ALL .xml links,
    then pick the one containing <infoTable> (the holdings table).
    """
    base = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/"

    # Step 1: Get the filing directory index
    xml_candidates = []
    try:
        idx = requests.get(base, headers=HEADERS, timeout=10)
        if idx.status_code == 200:
            soup = BeautifulSoup(idx.text, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if href.lower().endswith(".xml"):
                    # Build full URL (links may be absolute or relative)
                    if href.startswith("/"):
                        full = "https://www.sec.gov" + href
                    elif href.startswith("http"):
                        full = href
                    else:
                        full = base + href
                    xml_candidates.append(full)
    except Exception as e:
        print(f"  [13F] index error: {e}")

    # Also try common hardcoded names as fallback
    for name in ["infotable.xml", "form13fInfoTable.xml", "informationtable.xml"]:
        xml_candidates.append(base + name)

    # Step 2: Try each XML — return the first one containing <infoTable>
    for url in xml_candidates:
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                text = r.text
                if "infoTable" in text or "infotable" in text.lower():
                    return url
        except Exception:
            continue

    return None


# ── Step 3: Parse XML holdings ────────────────────────────────────────────────

CUSIP_TICKER = {
    "037833100":"AAPL","023135106":"AMZN","02079K305":"GOOGL","594918104":"MSFT",
    "67066G104":"NVDA","88160R101":"TSLA","30303M102":"META","46090E103":"SPOT",
    "079679102":"AMD", "45866F104":"INTC","126650100":"CVX", "172967424":"C",
    "38141G104":"GS",  "46625H100":"JPM", "172967101":"BAC","025816109":"AXP",
    "097023105":"BRK", "38259P508":"GOOG","693475105":"OXY","084670702":"BRK.B",
    "191241100":"KO",  "235851102":"CVS", "345370860":"WFC","92826C839":"V",
    "00206R102":"T",   "020002101":"MCD", "742718109":"PG", "857477103":"SBUX",
    "881624209":"TGT", "91324P102":"UNH", "531229102":"LLY","422806109":"HD",
    "26875P101":"EOG", "26614N102":"DUK", "67011P100":"NOC","526057104":"LMT",
    "375558103":"GILD","458140100":"INTC","56585A102":"MA", "713448108":"PFE",
    # Berkshire common holdings
    "693475105":"OXY", "084670702":"BRK.B","191241100":"KO", "060505104":"BAC",
    "166764100":"CVX", "717081103":"PFE",  "88160R101":"TSLA","806857108":"SHW",
    "08180D106":"BYD", "38141G104":"GS",   "46625H100":"JPM", "247361702":"KHC",
    "756109104":"RAL", "G7690C108":"STNE", "92826C839":"V",   "92826C839":"VISA",
    "00287Y109":"ABBV","256135203":"DVA",  "369604103":"GEN",  "882508104":"TRV",
    "30231G102":"XOM", "30303M102":"META", "023135106":"AMZN","023135106":"AMZN",
}

def _parse_xml(xml_text: str) -> List[Holding]:
    holdings = []
    try:
        # Strip namespaces for easier parsing
        xml_clean = re.sub(r' xmlns[^"]*"[^"]*"', '', xml_text)
        xml_clean = re.sub(r'<\?xml[^>]*\?>', '', xml_clean)

        from xml.etree import ElementTree as ET
        root = ET.fromstring(xml_clean)

        # Handle both namespaced and plain elements
        for info in root.iter():
            if info.tag.lower().endswith("infotable"):
                def get(tag):
                    # Try exact, try lowercase, try with namespace
                    for child in info:
                        if child.tag.lower().endswith(tag.lower()):
                            return (child.text or "").strip()
                    return ""

                name     = get("nameOfIssuer")
                cusip    = get("cusip")
                value    = get("value")
                shares   = get("sshPrnamt") or get("sshprnamt")
                put_call = get("putCall") or get("putcall")

                if name and cusip:
                    try:
                        # SEC value field is in dollars (confirmed from raw XML)
                        v = int(re.sub(r"[^0-9]", "", value)) if value else 0
                        s = int(re.sub(r"[^0-9]", "", shares)) if shares else 0
                    except ValueError:
                        v, s = 0, 0

                    ticker = CUSIP_TICKER.get(cusip, "")
                    # 13F value is already in $thousands — don't multiply again
                    holdings.append(Holding(
                        name=name, ticker=ticker, cusip=cusip,
                        shares=s, value_usd=v,  # v is in $thousands
                        put_call=put_call or "",
                    ))
    except Exception as e:
        print(f"  [13F] XML parse error: {e}")
    return sorted(holdings, key=lambda x: x.value_usd, reverse=True)


# ── Main fetch function ────────────────────────────────────────────────────────

def fetch_13f(entity_name: str, cik: str) -> Optional[Filing13F]:
    if not cik:
        return None
    info = _get_latest_13f_info(cik)
    if not info:
        print(f"  [13F] No 13F found for {entity_name}")
        return None

    time.sleep(0.25)  # polite rate limiting

    xml_url = _try_xml_names(info["cik_int"], info["accession"])
    if not xml_url:
        print(f"  [13F] XML not found for {entity_name} ({info['period']})")
        return Filing13F(entity_name=entity_name, cik=cik,
                         period=info["period"], filed_date=info["filed_date"],
                         total_value_usd=0)

    try:
        r = requests.get(xml_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        holdings = _parse_xml(r.text)
        total    = sum(h.value_usd for h in holdings)
        print(f"  [13F] ✓ {entity_name}: {len(holdings)} holdings, ${total/1e9:.1f}B AUM ({info['period']})")
        return Filing13F(entity_name=entity_name, cik=cik,
                         period=info["period"], filed_date=info["filed_date"],
                         total_value_usd=total, holdings=holdings[:30])
    except Exception as e:
        print(f"  [13F] fetch error for {entity_name}: {e}")
        return None


# ── ARK Daily ─────────────────────────────────────────────────────────────────

def fetch_ark_holdings(fund: str = "ARKK") -> List[Dict]:
    from config.whales import ARK_FUNDS
    url = ARK_FUNDS.get(fund)
    if not url:
        return []
    try:
        r = requests.get(url, headers=WEB_HEADERS, timeout=12)
        lines = [l for l in r.text.strip().split("\n") if l.strip()]
        holdings = []
        for line in lines[1:]:
            parts = [p.strip().strip('"') for p in line.split(",")]
            if len(parts) < 6:
                continue
            ticker = parts[3] if len(parts) > 3 else ""
            name   = parts[2] if len(parts) > 2 else ""
            try:
                shares = int(parts[5].replace(",", "")) if parts[5] else 0
                weight = float(parts[7].replace("%","")) if len(parts) > 7 and parts[7] else 0
            except (ValueError, IndexError):
                shares, weight = 0, 0
            if ticker:
                holdings.append({"fund": fund, "ticker": ticker,
                                  "name": name, "shares": shares, "weight_pct": weight})
        return sorted(holdings, key=lambda x: x["weight_pct"], reverse=True)[:20]
    except Exception as e:
        print(f"  [ARK] fetch error: {e}")
        return []


# ── Congressional Trades (Capitol Trades scraper) ─────────────────────────────

def fetch_capitol_trades(limit: int = 20) -> List[Dict]:
    """
    Scrape capitoltrades.com for recent Congressional stock trades.
    HTML structure confirmed:
      col[0]: politician + party/chamber (concatenated)
      col[1]: company name + TICKER:US (concatenated)
      col[2]: filed date
      col[6]: buy/sell action
      col[7]: amount range
    """
    trades = []
    try:
        r = requests.get("https://www.capitoltrades.com/trades",
                         headers=WEB_HEADERS, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")

        for row in soup.select("tbody tr")[:limit * 2]:
            cells = [td.get_text(strip=True) for td in row.select("td")]
            if len(cells) < 7:
                continue

            # Extract ticker from company cell (e.g. "Alphabet IncGOOGL:US" → "GOOGL")
            company_raw = cells[1] if len(cells) > 1 else ""
            ticker_match = re.search(r"([A-Z]{1,5})(?::US)?$", company_raw)
            if not ticker_match:
                continue
            ticker  = ticker_match.group(1)
            company = re.sub(r"[A-Z]{1,5}(?::US)?$", "", company_raw).strip()

            # Extract politician (split on party keywords)
            pol_raw = cells[0]
            politician = re.split(r"(Republican|Democrat|Independent)", pol_raw)[0].strip()

            # Action
            action_raw = cells[6].lower() if len(cells) > 6 else ""
            action = "Purchase" if "buy" in action_raw else ("Sale" if "sell" in action_raw else cells[6])

            trades.append({
                "politician": politician[:30],
                "ticker":     ticker,
                "company":    company[:25],
                "action":     action,
                "amount":     cells[7] if len(cells) > 7 else "—",
                "filed_date": cells[2][:12] if len(cells) > 2 else "—",
            })
            if len(trades) >= limit:
                break

    except Exception as e:
        print(f"  [Capitol Trades] Error: {e}")
    return trades
