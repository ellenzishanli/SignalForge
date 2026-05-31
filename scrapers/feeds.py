"""RSS/Atom feeds: TechCrunch AI, arXiv AI, AI funding news."""
import feedparser
from dataclasses import dataclass
from typing import List
from datetime import datetime


@dataclass
class FeedItem:
    title: str
    summary: str
    url: str
    source: str
    published: str


FEEDS = {
    "TechCrunch AI":    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "VentureBeat AI":   "https://venturebeat.com/category/ai/feed/",
    "arXiv CS.AI":      "https://rss.arxiv.org/rss/cs.AI",
    "arXiv CS.LG":      "https://rss.arxiv.org/rss/cs.LG",
    "The Information AI": "https://www.theinformation.com/feed",
}


def fetch_feeds(max_per_source: int = 8) -> List[FeedItem]:
    items = []
    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_source]:
                summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
                # Strip HTML tags from summary
                from bs4 import BeautifulSoup
                summary = BeautifulSoup(summary, "html.parser").get_text()[:500]

                items.append(FeedItem(
                    title=entry.get("title", "").strip(),
                    summary=summary.strip(),
                    url=entry.get("link", ""),
                    source=source,
                    published=entry.get("published", str(datetime.now().date())),
                ))
        except Exception as e:
            print(f"[Feeds] Error fetching {source}: {e}")

    return items
