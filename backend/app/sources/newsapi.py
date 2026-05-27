from datetime import datetime, timezone, timedelta
from typing import Iterable
import httpx
from app.sources.base import BaseSource, IngestedArticle
from app.sources.article_scraper import fetch_article_body

NEWSAPI_URL = "https://newsapi.org/v2/everything"

DEFAULT_QUERIES = [
    "(sentenced OR sentencing OR sentence) AND (murder OR homicide)",
]


class NewsAPISource(BaseSource):
    name = "newsapi"
    source_type = "news_api"

    def fetch(self) -> Iterable[IngestedArticle]:
        api_key = self.config.get("api_key")
        if not api_key:
            return
        queries = self.config.get("queries") or DEFAULT_QUERIES
        # NewsAPI free tier delays articles by 24h, so a 24h lookback always
        # returns 0. Default to 30 days (free tier max); can be overridden.
        lookback_days = int(self.config.get("lookback_days", 30))
        from_iso = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%dT%H:%M:%SZ")

        for q in queries:
            params = {
                "q": q,
                "language": "en",
                "from": from_iso,
                "sortBy": "publishedAt",
                "pageSize": 100,
                "apiKey": api_key,
            }
            r = httpx.get(
                NEWSAPI_URL,
                params=params,
                timeout=30.0,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130.0.0.0 Safari/537.36",
                },
            )
            if r.status_code != 200:
                continue
            data = r.json()
            for a in data.get("articles", []):
                pub_at = None
                if a.get("publishedAt"):
                    try:
                        pub_at = datetime.fromisoformat(a["publishedAt"].replace("Z", "+00:00"))
                    except ValueError:
                        pub_at = None
                snippet = (a.get("content") or "") + "\n\n" + (a.get("description") or "")
                # NewsAPI's content/description is truncated; try fetching the
                # real article body so the LLM can pull court / judge / docket.
                body = fetch_article_body(a["url"])
                raw_text = body if body and len(body) > len(snippet) else snippet
                yield IngestedArticle(
                    url=a["url"],
                    title=a.get("title"),
                    published_at=pub_at,
                    raw_text=raw_text,
                    source_name=a.get("source", {}).get("name") or "NewsAPI",
                    source_type="news_api",
                )
