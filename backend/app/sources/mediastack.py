from datetime import datetime, timezone, timedelta
from typing import Iterable
import httpx
from app.sources.base import BaseSource, IngestedArticle

MEDIASTACK_URL = "http://api.mediastack.com/v1/news"

DEFAULT_QUERIES = [
    "sentenced,murder",
    "sentenced,homicide",
    "convicted,manslaughter,sentenced",
    "life without parole,sentenced",
    "sentenced to death",
]


class MediaStackSource(BaseSource):
    name = "mediastack"
    source_type = "news_api"

    def fetch(self) -> Iterable[IngestedArticle]:
        api_key = self.config.get("api_key")
        if not api_key:
            return
        queries = self.config.get("queries") or DEFAULT_QUERIES
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        date_range = f"{yesterday},{today}"

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
                raw_text = title + "\n\n" + description
                yield IngestedArticle(
                    url=a["url"],
                    title=title or None,
                    published_at=pub_at,
                    raw_text=raw_text,
                    source_name=a.get("source") or "MediaStack",
                    source_type="news_api",
                )
