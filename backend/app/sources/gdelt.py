from datetime import datetime, timezone
from typing import Iterable
import httpx
from app.sources.base import BaseSource, IngestedArticle

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

DEFAULT_QUERIES = [
    'sentenced AND (murder OR homicide) sourcecountry:US',
    'sentenced AND manslaughter sourcecountry:US',
    '"life without parole" sourcecountry:US',
    '"sentenced to death" sourcecountry:US',
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

        for q in queries:
            params = {
                "query": q,
                "mode": "ArtList",
                "format": "json",
                "timespan": "24H",
                "maxrecords": 250,
                "sort": "DateDesc",
            }
            r = httpx.get(GDELT_URL, params=params, timeout=30.0)
            if r.status_code != 200:
                continue
            data = r.json()
            for a in data.get("articles", []):
                title = a.get("title") or ""
                yield IngestedArticle(
                    url=a["url"],
                    title=title or None,
                    published_at=_parse_seendate(a.get("seendate")),
                    raw_text=title,
                    source_name=a.get("domain") or "GDELT",
                    source_type="gdelt",
                )
