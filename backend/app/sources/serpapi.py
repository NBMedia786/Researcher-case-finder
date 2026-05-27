from datetime import datetime, timezone
from typing import Iterable
from email.utils import parsedate_to_datetime
import httpx
from app.sources.base import BaseSource, IngestedArticle
from app.sources.article_scraper import fetch_article_body

SERPAPI_URL = "https://serpapi.com/search"

# Google News indexes far more local outlets (KTLA, WBRC, county prosecutor
# press releases, etc.) than GDELT or NewsAPI catch. This is the source that
# replicates what Claude's web-search results look like.
DEFAULT_QUERIES = [
    "sentenced murder",
    "sentenced homicide",
    "sentence murder",
    "sentence homicide",
    "sentencing murder",
    "sentencing homicide",
]


class SerpAPISource(BaseSource):
    name = "serpapi"
    source_type = "web_search"

    def fetch(self) -> Iterable[IngestedArticle]:
        api_key = self.config.get("api_key")
        if not api_key or api_key.startswith("PASTE_"):
            return
        queries = self.config.get("queries") or DEFAULT_QUERIES

        for q in queries:
            # NOTE: SerpAPI's documented auth mechanism is the `api_key` query
            # parameter — they do not support Authorization headers. The key
            # is only ever sent outbound over HTTPS to serpapi.com; httpx
            # does not log request URLs, and we never echo the params dict
            # in exception handlers. If a future logging middleware is added,
            # it MUST scrub `api_key` from URLs before emission.
            params = {
                "engine": "google_news",
                "q": q,
                "gl": "us",
                "hl": "en",
                "api_key": api_key,
            }
            try:
                r = httpx.get(SERPAPI_URL, params=params, timeout=45.0)
                if r.status_code != 200:
                    continue
                data = r.json()
            except (httpx.HTTPError, ValueError):
                continue

            for a in data.get("news_results", []) or []:
                url = a.get("link")
                if not url:
                    continue
                title = a.get("title") or ""
                snippet = a.get("snippet") or ""
                pub_at = None
                # Google News date format: "5 hours ago", absolute ISO, or RFC822
                raw_date = a.get("date") or ""
                if raw_date:
                    try:
                        pub_at = parsedate_to_datetime(raw_date)
                    except (ValueError, TypeError):
                        try:
                            pub_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                        except ValueError:
                            pub_at = None
                if pub_at is None:
                    pub_at = datetime.now(timezone.utc)

                body = fetch_article_body(url)
                raw_text = body if body and len(body) > len(snippet) else f"{title}\n\n{snippet}"
                source_name = (a.get("source") or {}).get("name") if isinstance(a.get("source"), dict) else (a.get("source") or "Google News")

                yield IngestedArticle(
                    url=url,
                    title=title or None,
                    published_at=pub_at,
                    raw_text=raw_text,
                    source_name=source_name or "Google News",
                    source_type="web_search",
                )
