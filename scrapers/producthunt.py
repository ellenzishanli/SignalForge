import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List


@dataclass
class PHProduct:
    name: str
    tagline: str
    votes: int
    url: str
    topics: List[str]


def fetch_producthunt_top() -> List[PHProduct]:
    url = "https://www.producthunt.com/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 403:
            # PH blocks bots — return empty gracefully, briefing still works
            return []
        resp.raise_for_status()
    except Exception as e:
        print(f"[ProductHunt] Error fetching: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    products = []

    # PH renders dynamically but we can grab what's server-side rendered
    for item in soup.select("section[data-test='post-item']")[:15]:
        try:
            name_el = item.select_one("h3")
            name = name_el.get_text(strip=True) if name_el else "Unknown"

            tagline_el = item.select_one("p")
            tagline = tagline_el.get_text(strip=True) if tagline_el else ""

            votes_el = item.select_one("[data-test='vote-button']")
            votes = 0
            if votes_el:
                try:
                    votes = int(votes_el.get_text(strip=True).replace(",", ""))
                except ValueError:
                    pass

            link_el = item.select_one("a[href*='/posts/']")
            ph_url = "https://www.producthunt.com" + link_el["href"] if link_el else ""

            products.append(PHProduct(
                name=name,
                tagline=tagline,
                votes=votes,
                url=ph_url,
                topics=[],
            ))
        except Exception:
            continue

    # Fallback: grab any product names visible
    if not products:
        for link in soup.select("a[href*='/posts/']")[:15]:
            text = link.get_text(strip=True)
            if text and len(text) > 3:
                products.append(PHProduct(
                    name=text,
                    tagline="",
                    votes=0,
                    url="https://www.producthunt.com" + link["href"],
                    topics=[],
                ))

    return products
