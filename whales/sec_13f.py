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
    value_usd: int        # in dollars (raw SEC value field)
    put_call: str         # "" | "Put" | "Call"
    pct_of_portfolio: float = 0.0  # % of fund's total AUM


@dataclass
class Filing13F:
    entity_name: str
    cik: str
    period: str
    filed_date: str
    total_value_usd: int
    holdings: List[Holding] = field(default_factory=list)


# ── Step 1: Get latest 13F accession number ───────────────────────────────────

def _get_13f_info_list(cik: str, max_count: int = 4) -> List[dict]:
    """Return the N most recent 13F-HR filing infos for a CIK (for QoQ comparison)."""
    cik_padded = cik.lstrip("0").zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    results = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        data = r.json()
        filings = data.get("filings", {}).get("recent", {})
        forms   = filings.get("form", [])
        accs    = filings.get("accessionNumber", [])
        dates   = filings.get("filingDate", [])
        periods = filings.get("reportDate", [])
        for i, form in enumerate(forms):
            if form in ("13F-HR", "13F-HR/A"):
                results.append({
                    "accession_raw": accs[i],
                    "accession":     accs[i].replace("-", ""),
                    "filed_date":    dates[i],
                    "period":        periods[i],
                    "cik_int":       str(int(cik.lstrip("0") or "0")),
                })
                if len(results) >= max_count:
                    break
    except Exception as e:
        print(f"  [13F] submissions error for CIK {cik}: {e}")
    return results


def _get_latest_13f_info(cik: str) -> Optional[dict]:
    infos = _get_13f_info_list(cik, max_count=1)
    return infos[0] if infos else None


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
    # Mega-cap tech
    "037833100":"AAPL","023135106":"AMZN","02079K305":"GOOGL","594918104":"MSFT",
    "67066G104":"NVDA","88160R101":"TSLA","30303M102":"META","46090E103":"SPOT",
    "38259P508":"GOOG","079679102":"AMD","45866F104":"INTC","56585A102":"MA",
    "92826C839":"V","74144T108":"PYPL","17275R102":"CSCO","11135F101":"BKNG",
    "84265V105":"SHOP","09857L108":"UBER","20030N101":"COIN","14040H105":"CRWD",
    "67066G104":"NVDA","89832Q109":"TTD","09243R106":"BILL",
    # Finance
    "46625H100":"JPM","172967101":"BAC","38141G104":"GS","172967424":"C",
    "025816109":"AXP","345370860":"WFC","693475105":"OXY","00206R102":"T",
    "60934N104":"MS",  "06738G103":"BX", "18673P208":"BLK","26884L109":"ARES",
    "23804L103":"DFS", "29379V103":"EQT","48128B104":"KKR",
    # Healthcare / pharma
    "531229102":"LLY","91324P102":"UNH","713448108":"PFE","375558103":"GILD",
    "584934BX":"MRK", "00287Y109":"ABBV","256135203":"DVA","071734107":"BIIB",
    "04607L109":"ASND","14832Q200":"CBST","30067T106":"ELV",
    # Energy / industrials
    "126650100":"CVX","30231G102":"XOM","26875P101":"EOG","26614N102":"DUK",
    "67011P100":"NOC","526057104":"LMT","92204A306":"RTX","082811103":"BA",
    "806857108":"SHW","369604103":"GEN","882508104":"TRV",
    # Consumer / retail
    "191241100":"KO","742718109":"PG","020002101":"MCD","857477103":"SBUX",
    "881624209":"TGT","422806109":"HD","247361702":"KHC","084670702":"BRK.B",
    "060505104":"BAC","166764100":"CVX",
    # ETFs (common in quant fund 13Fs)
    "78462F103":"SPY","46429B267":"IVV","922908769":"QQQ","78463X107":"GLD",
    "46434G103":"IWM","78464A474":"EEM","73935A104":"TLT","464287622":"HYG",
    "78468R671":"XLK","81369Y704":"XLF","78468R309":"XLE","81369Y407":"XLV",
    "78468R200":"XLI","81369Y571":"XLC","921937835":"VTI","922908629":"VEA",
    # High-profile individual names
    "G7690C108":"STNE","08180D106":"BYD","00287Y109":"ABBV","09857L108":"UBER",
    "67401P104":"OKTA","097930109":"AMT","80180A102":"SBA", "87612E106":"TDG",
    "55315J102":"MPWR","83406F102":"SNAP","31620M106":"FANG","42809H107":"HES",
    "404121105":"HUBS","45168D104":"INTU","832696405":"SMH",
}

# Lazy-loaded name→ticker map built from SEC company_tickers.json
_NAME_TICKER_CACHE: dict = {}

def _get_name_ticker_map() -> dict:
    """Load SEC's company_tickers.json and build normalised name→ticker map."""
    global _NAME_TICKER_CACHE
    if _NAME_TICKER_CACHE:
        return _NAME_TICKER_CACHE
    try:
        r = requests.get("https://www.sec.gov/files/company_tickers.json",
                         headers=HEADERS, timeout=10)
        if r.status_code == 200:
            for v in r.json().values():
                name = v.get("title", "").upper().strip()
                ticker = v.get("ticker", "").strip()
                if name and ticker:
                    _NAME_TICKER_CACHE[name] = ticker
                    # Also index a shortened version
                    short = re.sub(r'\s+(INC|CORP|LTD|LLC|CO|PLC|LP|GROUP|HOLDINGS?|CLASS\s+[AB])\.?$', '', name).strip()
                    if short != name:
                        _NAME_TICKER_CACHE[short] = ticker
    except Exception:
        pass
    return _NAME_TICKER_CACHE

def _resolve_ticker(cusip: str, issuer_name: str) -> str:
    """Return ticker from CUSIP dict, fallback to name lookup."""
    if cusip in CUSIP_TICKER:
        return CUSIP_TICKER[cusip]
    name_map = _get_name_ticker_map()
    name_upper = issuer_name.upper().strip()
    # Try exact match
    if name_upper in name_map:
        return name_map[name_upper]
    # Try stripping common suffixes
    for suffix in [" INC", " CORP", " LTD", " LLC", " CO", " PLC", " LP",
                   " CLASS A", " CLASS B", " DEL", " COM", " NEW"]:
        short = name_upper.replace(suffix, "").strip()
        if short in name_map:
            return name_map[short]
    return ""

def _parse_xml(xml_text: str) -> List[Holding]:
    holdings = []
    try:
        # Strip XML declaration
        xml_clean = re.sub(r'<\?xml[^>]*\?>', '', xml_text)
        # Strip all namespace declarations: xmlns="..." and xmlns:prefix="..."
        xml_clean = re.sub(r'\s+xmlns(?::\w+)?="[^"]*"', '', xml_clean)
        # Strip namespace-qualified attributes: xsi:schemaLocation="..." etc.
        xml_clean = re.sub(r'\s+\w+:[a-zA-Z][a-zA-Z0-9_-]*="[^"]*"', '', xml_clean)
        # Strip namespace prefixes from element tags: <n1:foo> → <foo>, </n1:foo> → </foo>
        xml_clean = re.sub(r'<(/?)[\w.\-]+:([\w])', r'<\1\2', xml_clean)

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

                    ticker = _resolve_ticker(cusip, name)
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

def _fetch_filing(info: dict, entity_name: str, cik: str) -> Optional[Filing13F]:
    """Fetch and parse a single 13F filing given its info dict."""
    xml_url = _try_xml_names(info["cik_int"], info["accession"])
    if not xml_url:
        return Filing13F(entity_name=entity_name, cik=cik,
                         period=info["period"], filed_date=info["filed_date"],
                         total_value_usd=0)
    try:
        r = requests.get(xml_url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        holdings = _parse_xml(r.text)
        total = sum(h.value_usd for h in holdings)
        # Compute % of portfolio for each holding
        for h in holdings:
            h.pct_of_portfolio = round(h.value_usd / total * 100, 2) if total else 0.0
        return Filing13F(entity_name=entity_name, cik=cik,
                         period=info["period"], filed_date=info["filed_date"],
                         total_value_usd=total, holdings=holdings)
    except Exception as e:
        print(f"  [13F] fetch error for {entity_name}: {e}")
        return None


def fetch_13f(entity_name: str, cik: str, top_n: int = 60) -> Optional[Filing13F]:
    """Fetch latest 13F. Returns top_n holdings sorted by value."""
    if not cik:
        return None
    infos = _get_13f_info_list(cik, max_count=1)
    if not infos:
        print(f"  [13F] No 13F found for {entity_name}")
        return None
    time.sleep(0.25)
    filing = _fetch_filing(infos[0], entity_name, cik)
    if filing and filing.holdings:
        print(f"  [13F] ✓ {entity_name}: {len(filing.holdings)} holdings, "
              f"${filing.total_value_usd/1e9:.1f}B ({filing.period})")
        filing.holdings = filing.holdings[:top_n]
    return filing


def fetch_13f_with_changes(entity_name: str, cik: str, top_n: int = 60) -> Optional[Filing13F]:
    """
    Fetch latest 13F AND compare to previous quarter.
    Annotates each Holding with change vs prev quarter in put_call field:
      'NEW' | 'INCREASED' | 'DECREASED' | 'HOLD' | 'CLOSED'
    """
    if not cik:
        return None
    infos = _get_13f_info_list(cik, max_count=2)
    if not infos:
        print(f"  [13F] No 13F found for {entity_name}")
        return None

    time.sleep(0.25)
    current = _fetch_filing(infos[0], entity_name, cik)
    if not current or not current.holdings:
        return current

    # Build previous quarter CUSIP → value map
    prev_values: Dict[str, int] = {}
    if len(infos) > 1:
        time.sleep(0.25)
        prev = _fetch_filing(infos[1], entity_name, cik)
        if prev and prev.holdings:
            prev_values = {h.cusip: h.value_usd for h in prev.holdings}

    # Annotate changes
    for h in current.holdings:
        prev_v = prev_values.get(h.cusip, 0)
        if prev_v == 0 and h.value_usd > 0:
            change = "NEW"
        elif prev_v > 0 and h.value_usd == 0:
            change = "CLOSED"
        elif prev_v > 0:
            ratio = h.value_usd / prev_v
            if ratio >= 1.25:
                change = "INCREASED"
            elif ratio <= 0.75:
                change = "DECREASED"
            else:
                change = "HOLD"
        else:
            change = "HOLD"
        # Encode change in put_call field to avoid schema change
        h.put_call = f"chg:{change}" if not h.put_call else h.put_call

    print(f"  [13F] ✓ {entity_name}: {len(current.holdings)} holdings "
          f"${current.total_value_usd/1e9:.1f}B ({current.period}) "
          f"[vs {infos[1]['period'] if len(infos)>1 else 'no prev'}]")
    current.holdings = current.holdings[:top_n]
    return current


# ── ARK Daily ─────────────────────────────────────────────────────────────────

def fetch_ark_holdings(fund: str = "ARKK") -> List[Dict]:
    """Fetch ARK ETF holdings from arkfunds.io API (ark-funds.com CSV is geo-blocked)."""
    try:
        url = f"https://arkfunds.io/api/v2/etf/holdings?symbol={fund}"
        r = requests.get(url, headers=WEB_HEADERS, timeout=12)
        if r.status_code != 200:
            return []
        raw = r.json()
        # API returns {"holdings": [...]} or {"data": [...]}
        items = raw.get("holdings") or raw.get("data") or []
        holdings = []
        for h in items:
            ticker = (h.get("ticker") or "").strip()
            name   = (h.get("company") or h.get("name") or ticker)[:30]
            weight = float(h.get("weight", h.get("weight_pct", 0)) or 0)
            shares = int(h.get("shares", 0) or 0)
            if ticker and re.match(r'^[A-Z]{1,5}$', ticker):
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
