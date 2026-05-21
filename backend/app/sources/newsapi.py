from datetime import datetime, timezone, timedelta
from typing import Iterable
import httpx
from app.sources.base import BaseSource, IngestedArticle
from app.sources.article_scraper import fetch_article_body

NEWSAPI_URL = "https://newsapi.org/v2/everything"

DEFAULT_QUERIES = [
    '"sentenced to life" murder',
    '"sentenced to death"',
    '"life without parole" sentenced',
    '"convicted of murder" sentenced',
    '"sentenced to" manslaughter',
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
        # returns 0. Default to 7 days; can be overridden via config.
        lookback_days = int(self.config.get("lookback_days", 7))
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
            r = httpx.get(NEWSAPI_URL, params=params, timeout=30.0)
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
