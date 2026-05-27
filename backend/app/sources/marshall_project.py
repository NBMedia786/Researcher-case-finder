"""The Marshall Project — nonprofit criminal-justice journalism.

High signal-to-noise for our use case because they specifically cover
sentencings, plea deals, and case outcomes that mainstream outlets skip.
Same RSS-filter pattern as the DOJ source.
"""

from datetime import datetime
from typing import Iterable
from email.utils import parsedate_to_datetime
import httpx
import feedparser
from app.sources.base import BaseSource, IngestedArticle
from app.sources.article_scraper import fetch_article_body

DEFAULT_FEEDS = ["https://www.themarshallproject.org/feed/all.rss"]

SENTENCE_TERMS = ("sentenced", "sentencing", "sentence")
HOMICIDE_TERMS = ("murder", "homicide")


def _looks_like_homicide_sentencing(title: str, description: str) -> bool:
    blob = f"{title} {description}".lower()
    has_sentence = any(k in blob for k in SENTENCE_TERMS)
    has_homicide = any(k in blob for k in HOMICIDE_TERMS)
    return has_sentence and has_homicide


class MarshallProjectSource(BaseSource):
    name = "marshall_project"
    source_type = "rss"

    def fetch(self) -> Iterable[IngestedArticle]:
        feeds = self.config.get("feeds") or DEFAULT_FEEDS
        for feed_url in feeds:
            try:
                r = httpx.get(feed_url, timeout=30.0, follow_redirects=True)
                if r.status_code != 200:
                    continue
                parsed = feedparser.parse(r.text)
            except Exception:
                continue
            for entry in parsed.entries:
                title = getattr(entry, "title", "") or ""
                desc = getattr(entry, "description", "") or getattr(entry, "summary", "") or ""
                if not _looks_like_homicide_sentencing(title, desc):
                    continue
                pub = None
                if getattr(entry, "published", None):
                    try:
                        pub = parsedate_to_datetime(entry.published)
                    except Exception:
                        pub = None
                url = getattr(entry, "link", "")
                if not url:
                    continue
                body = fetch_article_body(url)
                raw_text = body if body and len(body) > len(desc) else f"{title}\n\n{desc}"
                yield IngestedArticle(
                    url=url,
                    title=title,
                    published_at=pub,
                    raw_text=raw_text,
                    source_name="The Marshall Project",
                    source_type="rss",
                )
