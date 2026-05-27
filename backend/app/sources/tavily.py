from datetime import datetime, timezone
from typing import Iterable
import httpx
from app.sources.base import BaseSource, IngestedArticle
from app.sources.article_scraper import fetch_article_body

TAVILY_URL = "https://api.tavily.com/search"

# Tavily is an LLM-optimized web search API — natural-language friendly,
# returns clean snippets + URLs. Free tier: 1000 searches/month.
DEFAULT_QUERIES = [
    "US homicide sentencing this week",
    "convicted of murder sentenced life prison",
    "sentenced to death murder verdict",
    "life without parole sentenced homicide",
    "first-degree murder sentencing US court",
    "manslaughter sentenced years prison verdict",
]


class TavilySource(BaseSource):
    name = "tavily"
    source_type = "web_search"

    def fetch(self) -> Iterable[IngestedArticle]:
        api_key = self.config.get("api_key")
        if not api_key or api_key.startswith("PASTE_"):
            return
        queries = self.config.get("queries") or DEFAULT_QUERIES
        max_results = int(self.config.get("max_results", 20))

        for q in queries:
            payload = {
                "api_key": api_key,
                "query": q,
                "search_depth": "advanced",
                "topic": "news",
                "max_results": max_results,
                "include_answer": False,
                "include_raw_content": False,
                "days": 7,
            }
            try:
                r = httpx.post(TAVILY_URL, json=payload, timeout=45.0)
                if r.status_code != 200:
                    continue
                data = r.json()
            except (httpx.HTTPError, ValueError):
                continue

            for a in data.get("results", []) or []:
                url = a.get("url")
                if not url:
                    continue
                title = a.get("title") or ""
                content = a.get("content") or ""
                pub_at = None
                if a.get("published_date"):
                    try:
                        pub_at = datetime.fromisoformat(a["published_date"].replace("Z", "+00:00"))
                    except ValueError:
                        pub_at = None
                if pub_at is None:
                    pub_at = datetime.now(timezone.utc)

                body = fetch_article_body(url)
                raw_text = body if body and len(body) > len(content) else f"{title}\n\n{content}"

                yield IngestedArticle(
                    url=url,
                    title=title or None,
                    published_at=pub_at,
                    raw_text=raw_text,
                    source_name="Tavily Web Search",
                    source_type="web_search",
                )
