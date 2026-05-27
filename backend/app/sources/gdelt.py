from datetime import datetime, timezone
from typing import Iterable
import httpx
from app.sources.base import BaseSource, IngestedArticle
from app.sources.article_scraper import fetch_article_body

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# GDELT DOC API supports boolean queries; sourcecountry:US restricts to
# articles from US-based publishers (which is where US homicide sentencings
# are actually covered). Queries are deliberately broader than NewsAPI's
# because GDELT indexes thousands of local papers NewsAPI never sees.
DEFAULT_QUERIES = [
    "sentenced murder sourcecountry:US",
    "sentenced homicide sourcecountry:US",
    "sentence murder sourcecountry:US",
    "sentence homicide sourcecountry:US",
    "sentencing murder sourcecountry:US",
    "sentencing homicide sourcecountry:US",
]


def _parse_seendate(seendate: str) -> datetime | None:
    """Parse GDELT seendate format: YYYYMMDDTHHMMSSZ"""
    try:
        return datetime.strptime(seendate, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


class GdeltSource(BaseSource):
    name = "gdelt"
    source_type = "gdelt"

    def fetch(self) -> Iterable[IngestedArticle]:
        queries = self.config.get("queries") or DEFAULT_QUERIES
        # GDELT timespan accepts e.g. "24H", "7d", "30d", "1m". Default to
        # 30 days so retrospective runs catch recent sentencings.
        timespan = self.config.get("timespan", "30d")

        for q in queries:
            params = {
                "query": q,
                "mode": "ArtList",
                "format": "json",
                "timespan": timespan,
                "maxrecords": 250,
                "sort": "DateDesc",
            }
            r = httpx.get(GDELT_URL, params=params, timeout=30.0)
            if r.status_code != 200:
                continue
            try:
                data = r.json()
            except ValueError:
                # GDELT occasionally returns non-JSON HTML when overloaded
                continue
            for a in data.get("articles", []):
                title = a.get("title") or ""
                # Scrape the full article body so Gemini can pull court,
                # judge, docket — title alone is far too thin to extract.
                body = fetch_article_body(a["url"])
                raw_text = body if body and len(body) > len(title) else title
                yield IngestedArticle(
                    url=a["url"],
                    title=title or None,
                    published_at=_parse_seendate(a.get("seendate")),
                    raw_text=raw_text,
                    source_name=a.get("domain") or "GDELT",
                    source_type="gdelt",
                )
