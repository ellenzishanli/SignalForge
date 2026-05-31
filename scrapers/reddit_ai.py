"""Reddit AI community posts - works with or without API credentials."""
import os
import requests
from dataclasses import dataclass
from typing import List


@dataclass
class RedditPost:
    title: str
    score: int
    num_comments: int
    url: str
    subreddit: str
    selftext: str


SUBREDDITS = ["artificial", "MachineLearning", "LocalLLaMA", "singularity", "AIStartups"]


def fetch_reddit_hot(max_per_sub: int = 5) -> List[RedditPost]:
    posts = []
    headers = {"User-Agent": "FrontierTechRadar/1.0 (research tool)"}

    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")

    if client_id and client_secret:
        # Authenticated - better rate limits
        try:
            auth = requests.auth.HTTPBasicAuth(client_id, client_secret)
            token_resp = requests.post(
                "https://www.reddit.com/api/v1/access_token",
                auth=auth,
                data={"grant_type": "client_credentials"},
                headers={"User-Agent": headers["User-Agent"]},
                timeout=10,
            )
            token = token_resp.json().get("access_token", "")
            headers["Authorization"] = f"bearer {token}"
            base = "https://oauth.reddit.com"
        except Exception:
            base = "https://www.reddit.com"
    else:
        base = "https://www.reddit.com"

    for sub in SUBREDDITS:
        try:
            url = f"{base}/r/{sub}/hot.json?limit={max_per_sub}"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                print(f"[Reddit] r/{sub} returned {resp.status_code}, skipping")
                continue
            data = resp.json()
            for child in data.get("data", {}).get("children", []):
                p = child["data"]
                posts.append(RedditPost(
                    title=p.get("title", ""),
                    score=p.get("score", 0),
                    num_comments=p.get("num_comments", 0),
                    url="https://reddit.com" + p.get("permalink", ""),
                    subreddit=sub,
                    selftext=p.get("selftext", "")[:300],
                ))
        except Exception as e:
            print(f"[Reddit] Error fetching r/{sub}: {e}")

    return sorted(posts, key=lambda x: x.score, reverse=True)
