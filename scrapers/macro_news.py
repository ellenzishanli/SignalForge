"""
Macro News Scraper — fetches latest financial headlines from free RSS feeds.

Sources:
  - Reuters Business
  - Yahoo Finance
  - CNBC
  - MarketWatch
  - BBC Business

Usage:
    from scrapers.macro_news import fetch_macro_headlines
    headlines = fetch_macro_headlines()  # -> list[dict]
"""
import feedparser
from datetime import datetime

_FEEDS = [
    ("Reuters",     "https://feeds.reuters.com/reuters/businessNews"),
    ("Yahoo Finance","https://finance.yahoo.com/news/rssindex"),
    ("CNBC",        "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("MarketWatch", "https://feeds.marketwatch.com/marketwatch/topstories/"),
    ("BBC Business","http://feeds.bbci.co.uk/news/business/rss.xml"),
]

_PER_SOURCE = 6
_MAX_TOTAL  = 30


def _parse_entry(entry, source: str) -> dict:
    """Extract relevant fields from a feedparser entry."""
    title   = getattr(entry, "title",   "") or ""
    summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
    link    = getattr(entry, "link",    "") or ""
    # feedparser gives published_parsed as a time.struct_time
    published = ""
    if hasattr(entry, "published"):
        published = entry.published
    elif hasattr(entry, "updated"):
        published = entry.updated

    # Strip HTML tags from summary (very basic)
    import re
    summary = re.sub(r"<[^>]+>", " ", summary).strip()
    summary = re.sub(r"\s+", " ", summary)

    return {
        "title":     title.strip(),
        "summary":   summary[:400],
        "source":    source,
        "published": published,
        "link":      link.strip(),
    }


def fetch_macro_headlines() -> list[dict]:
    """
    Fetch the latest financial headlines from multiple RSS feeds.

    Returns a deduplicated list of dicts with keys:
        title, summary, source, published, link
    Capped at 30 entries total (6 per source).
    One source failing does not affect the others.
    """
    seen_titles: set[str] = set()
    results: list[dict] = []

    for source_name, url in _FEEDS:
        try:
            feed = feedparser.parse(url)
            entries = feed.entries[:_PER_SOURCE]
            for entry in entries:
                item = _parse_entry(entry, source_name)
                # Deduplicate by normalised title
                key = item["title"].lower().strip()
                if not key or key in seen_titles:
                    continue
                seen_titles.add(key)
                results.append(item)
        except Exception as exc:
            # One source failing should not crash the rest
            print(f"[macro_news] Warning: failed to fetch {source_name} ({url}): {exc}")

    return results[:_MAX_TOTAL]
