"""Bing News Search API (via Azure Cognitive Services).

Free F1 tier: 1,000 transactions/month. Different index from Google →
catches stories SerpAPI misses. Get a subscription key at
https://portal.azure.com/ (create a "Bing Search v7" resource).
"""

from datetime import datetime, timezone
from typing import Iterable
import httpx
from app.sources.base import BaseSource, IngestedArticle
from app.sources.article_scraper import fetch_article_body

BING_URL = "https://api.bing.microsoft.com/v7.0/news/search"

DEFAULT_QUERIES = [
    "sentenced murder",
    "sentenced homicide",
    "sentence murder",
    "sentence homicide",
    "sentencing murder",
    "sentencing homicide",
]


class BingNewsSource(BaseSource):
    name = "bing_news"
    source_type = "web_search"

    def fetch(self) -> Iterable[IngestedArticle]:
        api_key = self.config.get("api_key")
        if not api_key or api_key.startswith("PASTE_"):
            return
        queries = self.config.get("queries") or DEFAULT_QUERIES

        headers = {"Ocp-Apim-Subscription-Key": api_key}
        for q in queries:
            params = {
                "q": q,
                "mkt": "en-US",
                "count": 50,
                "freshness": "Week",
                "safeSearch": "Off",
                "sortBy": "Date",
            }
            try:
                r = httpx.get(BING_URL, params=params, headers=headers, timeout=30.0)
                if r.status_code != 200:
                    continue
                data = r.json()
            except (httpx.HTTPError, ValueError):
                continue
            for a in data.get("value", []) or []:
                url = a.get("url")
                if not url:
                    continue
                title = a.get("name") or ""
                description = a.get("description") or ""
                snippet = f"{title}\n\n{description}"
                pub_at = None
                if a.get("datePublished"):
                    try:
                        pub_at = datetime.fromisoformat(a["datePublished"].replace("Z", "+00:00"))
                    except ValueError:
                        pub_at = None
                if pub_at is None:
                    pub_at = datetime.now(timezone.utc)
                body = fetch_article_body(url)
                raw_text = body if body and len(body) > len(snippet) else snippet
                provider = (a.get("provider") or [{}])
                source_name = (provider[0].get("name") if provider else None) or "Bing News"
                yield IngestedArticle(
                    url=url,
                    title=title or None,
                    published_at=pub_at,
                    raw_text=raw_text,
                    source_name=source_name,
                    source_type="web_search",
                )
