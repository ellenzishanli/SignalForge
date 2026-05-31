import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass, field
from typing import List


@dataclass
class GithubRepo:
    name: str
    description: str
    language: str
    stars_today: int
    total_stars: int
    url: str


def fetch_github_trending(language: str = "", since: str = "daily") -> List[GithubRepo]:
    url = f"https://github.com/trending/{language}?since={since}"
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"[GitHub] Error fetching: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    repos = []

    for article in soup.select("article.Box-row")[:20]:
        try:
            name_el = article.select_one("h2 a")
            name = name_el.get_text(strip=True).replace("\n", "").replace(" ", "") if name_el else ""
            repo_url = "https://github.com" + name_el["href"] if name_el else ""

            desc_el = article.select_one("p")
            description = desc_el.get_text(strip=True) if desc_el else ""

            lang_el = article.select_one("[itemprop='programmingLanguage']")
            language_used = lang_el.get_text(strip=True) if lang_el else "Unknown"

            stars_els = article.select("a.Link--muted")
            total_stars = 0
            if stars_els:
                try:
                    total_stars = int(stars_els[0].get_text(strip=True).replace(",", ""))
                except ValueError:
                    pass

            today_el = article.select_one("span.d-inline-block.float-sm-right")
            stars_today = 0
            if today_el:
                txt = today_el.get_text(strip=True)
                try:
                    stars_today = int("".join(filter(str.isdigit, txt.split("stars")[0])))
                except ValueError:
                    pass

            repos.append(GithubRepo(
                name=name,
                description=description,
                language=language_used,
                stars_today=stars_today,
                total_stars=total_stars,
                url=repo_url,
            ))
        except Exception:
            continue

    return repos
