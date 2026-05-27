from datetime import datetime, timezone, timedelta
from typing import Iterable
import httpx
from app.sources.base import BaseSource, IngestedArticle
from app.sources.article_scraper import fetch_article_body

MEDIASTACK_URL = "http://api.mediastack.com/v1/news"

# MediaStack uses comma-separated keywords (comma = AND). No OR support,
# so we enumerate every combination of sentence-verb × homicide-noun.
DEFAULT_QUERIES = [
    "sentenced,murder",
    "sentenced,homicide",
    "sentencing,murder",
    "sentencing,homicide",
    "sentence,murder",
    "sentence,homicide",
]


class MediaStackSource(BaseSource):
    name = "mediastack"
    source_type = "news_api"

    def fetch(self) -> Iterable[IngestedArticle]:
        api_key = self.config.get("api_key")
        # Skip if no key OR if it's a placeholder from .env.example
        if not api_key or api_key.startswith("PASTE_"):
            return
        queries = self.config.get("queries") or DEFAULT_QUERIES
        # MediaStack accepts a date range "YYYY-MM-DD,YYYY-MM-DD".
        # Default to last 30 days so retrospective runs catch recent
        # sentencings, not just today's news.
        lookback_days = int(self.config.get("lookback_days", 30))
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        date_range = f"{start},{today}"

        for q in queries:
            params = {
                "access_key": api_key,
                "keywords": q,
                "countries": "us",
                "languages": "en",
                "sort": "published_desc",
                "date": date_range,
                "limit": 100,
            }
            r = httpx.get(MEDIASTACK_URL, params=params, timeout=30.0)
            if r.status_code != 200:
                continue
            data = r.json()
            for a in data.get("data", []):
                pub_at = None
                if a.get("published_at"):
                    try:
                        pub_at = datetime.fromisoformat(a["published_at"].replace("Z", "+00:00"))
                    except ValueError:
                        pub_at = None
                title = a.get("title") or ""
                description = a.get("description") or ""
                snippet = title + "\n\n" + description
                # Try fetching the full body so the LLM can pull court / judge / docket
                body = fetch_article_body(a["url"])
                raw_text = body if body and len(body) > len(snippet) else snippet
                yield IngestedArticle(
                    url=a["url"],
                    title=title or None,
                    published_at=pub_at,
                    raw_text=raw_text,
                    source_name=a.get("source") or "MediaStack",
                    source_type="news_api",
                )
