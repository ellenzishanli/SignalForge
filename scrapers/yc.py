"""YC companies - latest batch from HN Who's Hiring and YC site."""
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List


@dataclass
class YCCompany:
    name: str
    description: str
    batch: str
    url: str
    tags: List[str]


def fetch_yc_latest(batch: str = "W25") -> List[YCCompany]:
    """Fetch recent YC companies from the YC company directory."""
    url = f"https://www.ycombinator.com/companies?batch={batch}"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"[YC] Error fetching: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    companies = []

    # YC renders via React, grab what's available in static HTML
    for card in soup.select("a._company_86jzd_338")[:30]:
        try:
            name_el = card.select_one("span._coName_86jzd_453")
            name = name_el.get_text(strip=True) if name_el else ""

            desc_el = card.select_one("span._coDescription_86jzd_478")
            description = desc_el.get_text(strip=True) if desc_el else ""

            href = card.get("href", "")
            company_url = "https://www.ycombinator.com" + href if href else ""

            tags = [t.get_text(strip=True) for t in card.select("span.pill")]

            if name:
                companies.append(YCCompany(
                    name=name,
                    description=description,
                    batch=batch,
                    url=company_url,
                    tags=tags,
                ))
        except Exception:
            continue

    return companies


def fetch_hn_who_is_hiring() -> List[dict]:
    """Get top HN 'Who is Hiring' thread for AI companies."""
    # Search for latest hiring thread
    url = "https://hn.algolia.com/api/v1/search?query=Ask+HN+Who+is+hiring&tags=story&hitsPerPage=3"
    try:
        resp = requests.get(url, timeout=10)
        hits = resp.json().get("hits", [])
        return [{"title": h["title"], "url": f"https://news.ycombinator.com/item?id={h['objectID']}"} for h in hits]
    except Exception:
        return []
