from datetime import datetime
from typing import Iterable
from email.utils import parsedate_to_datetime
import httpx
import feedparser
from app.sources.base import BaseSource, IngestedArticle

DEFAULT_FEEDS = ["https://www.justice.gov/news/rss"]

SENTENCE_TERMS = ("sentenced", "sentencing", "sentence")
HOMICIDE_TERMS = ("murder", "homicide")


def _looks_like_homicide_sentencing(title: str, description: str) -> bool:
    blob = f"{title} {description}".lower()
    has_sentence = any(k in blob for k in SENTENCE_TERMS)
    has_homicide = any(k in blob for k in HOMICIDE_TERMS)
    return has_sentence and has_homicide


class DOJSource(BaseSource):
    name = "doj"
    source_type = "doj"

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
                yield IngestedArticle(
                    url=entry.link,
                    title=title,
                    published_at=pub,
                    raw_text=desc,
                    source_name="DOJ",
                    source_type="doj",
                )
