"""GNews.io — 100 requests/day free tier.

Smaller free quota than NewsData but a slightly different index.
Get a key at https://gnews.io/register
"""

from datetime import datetime, timezone
from typing import Iterable
import httpx
from app.sources.base import BaseSource, IngestedArticle
from app.sources.article_scraper import fetch_article_body

GNEWS_URL = "https://gnews.io/api/v4/search"

DEFAULT_QUERIES = [
    "sentenced murder",
    "sentenced homicide",
    "sentence murder",
    "sentence homicide",
    "sentencing murder",
    "sentencing homicide",
]


class GNewsSource(BaseSource):
    name = "gnews"
    source_type = "news_api"

    def fetch(self) -> Iterable[IngestedArticle]:
        api_key = self.config.get("api_key")
        if not api_key or api_key.startswith("PASTE_"):
            return
        queries = self.config.get("queries") or DEFAULT_QUERIES

        for q in queries:
            params = {
                "q": q,
                "lang": "en",
                "country": "us",
                "max": 10,
                "token": api_key,
            }
            try:
                r = httpx.get(GNEWS_URL, params=params, timeout=30.0)
                if r.status_code != 200:
                    continue
                data = r.json()
            except (httpx.HTTPError, ValueError):
                continue
            for a in data.get("articles", []) or []:
                url = a.get("url")
                if not url:
                    continue
                title = a.get("title") or ""
                description = a.get("description") or ""
                content = a.get("content") or ""
                snippet = "\n\n".join(filter(None, [title, description, content]))
                pub_at = None
                if a.get("publishedAt"):
                    try:
                        pub_at = datetime.fromisoformat(a["publishedAt"].replace("Z", "+00:00"))
                    except ValueError:
                        pub_at = None
                if pub_at is None:
                    pub_at = datetime.now(timezone.utc)
                body = fetch_article_body(url)
                raw_text = body if body and len(body) > len(snippet) else snippet
                source_name = (a.get("source") or {}).get("name") or "GNews"
                yield IngestedArticle(
                    url=url,
                    title=title or None,
                    published_at=pub_at,
                    raw_text=raw_text,
                    source_name=source_name,
                    source_type="news_api",
                )
