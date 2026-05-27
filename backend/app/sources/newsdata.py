"""NewsData.io — 200 requests/day free tier.

Different index from NewsAPI/MediaStack; sometimes catches sources the
others miss. Get a key at https://newsdata.io/register
"""

from datetime import datetime, timezone
from typing import Iterable
import httpx
from app.sources.base import BaseSource, IngestedArticle
from app.sources.article_scraper import fetch_article_body

NEWSDATA_URL = "https://newsdata.io/api/1/news"

DEFAULT_QUERIES = [
    "sentenced murder",
    "sentenced homicide",
    "sentence murder",
    "sentence homicide",
    "sentencing murder",
    "sentencing homicide",
]


class NewsDataSource(BaseSource):
    name = "newsdata"
    source_type = "news_api"

    def fetch(self) -> Iterable[IngestedArticle]:
        api_key = self.config.get("api_key")
        if not api_key or api_key.startswith("PASTE_"):
            return
        queries = self.config.get("queries") or DEFAULT_QUERIES

        for q in queries:
            params = {
                "apikey": api_key,
                "q": q,
                "country": "us",
                "language": "en",
            }
            try:
                r = httpx.get(NEWSDATA_URL, params=params, timeout=30.0)
                if r.status_code != 200:
                    continue
                data = r.json()
            except (httpx.HTTPError, ValueError):
                continue
            for a in data.get("results", []) or []:
                url = a.get("link")
                if not url:
                    continue
                title = a.get("title") or ""
                description = a.get("description") or ""
                content = a.get("content") or ""
                snippet = "\n\n".join(filter(None, [title, description, content]))
                pub_at = None
                if a.get("pubDate"):
                    try:
                        pub_at = datetime.fromisoformat(a["pubDate"].replace("Z", "+00:00"))
                    except ValueError:
                        pub_at = None
                if pub_at is None:
                    pub_at = datetime.now(timezone.utc)
                body = fetch_article_body(url)
                raw_text = body if body and len(body) > len(snippet) else snippet
                source_name = a.get("source_id") or a.get("source_name") or "NewsData"
                yield IngestedArticle(
                    url=url,
                    title=title or None,
                    published_at=pub_at,
                    raw_text=raw_text,
                    source_name=source_name,
                    source_type="news_api",
                )
