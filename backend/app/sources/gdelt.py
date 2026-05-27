import time
from datetime import datetime, timezone
from typing import Iterable
import httpx
from app.sources.base import BaseSource, IngestedArticle
from app.sources.article_scraper import fetch_article_body

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# GDELT is famously rate-limited / overloaded and routinely refuses TCP
# connections or takes 20-30s to respond. We retry up to 3 times with
# linear backoff before giving up on a single query.
_MAX_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 3

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
            # If the query came from a Topic (no sourcecountry baked in),
            # append it so we stay US-only. Idempotent if already present.
            if "sourcecountry:" not in q:
                q = f"{q} sourcecountry:US"
            params = {
                "query": q,
                "mode": "ArtList",
                "format": "json",
                "timespan": timespan,
                "maxrecords": 250,
                "sort": "DateDesc",
            }
            # Retry the request up to _MAX_RETRIES times — GDELT regularly
            # refuses the first TCP handshake or returns non-JSON HTML under
            # load. A single bad query should NOT kill the whole source.
            data = None
            for attempt in range(_MAX_RETRIES):
                try:
                    # GDELT response times routinely hit 20-25s under load;
                    # 60s gives comfortable headroom on all phases.
                    r = httpx.get(GDELT_URL, params=params, timeout=60.0)
                    if r.status_code != 200:
                        break
                    data = r.json()
                    break
                except (httpx.HTTPError, ValueError):
                    if attempt < _MAX_RETRIES - 1:
                        time.sleep(_RETRY_BACKOFF_SECONDS * (attempt + 1))
                    continue
            if data is None:
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
