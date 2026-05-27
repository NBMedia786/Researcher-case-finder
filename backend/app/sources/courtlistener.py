from datetime import datetime, timezone, timedelta
from typing import Iterable
import httpx
from app.sources.base import BaseSource, IngestedArticle

COURTLISTENER_URL = "https://www.courtlistener.com/api/rest/v4/search/"

# CourtListener provides authoritative federal court records — opinions,
# dockets, sentencing memos. Different category from news scrapes: this is
# the ground truth. Free, optional API token (raises rate limit from 5000
# to 50000/day).
DEFAULT_QUERIES = [
    "(sentenced OR sentencing OR sentence) AND (murder OR homicide)",
]


class CourtListenerSource(BaseSource):
    name = "courtlistener"
    source_type = "court_records"

    def fetch(self) -> Iterable[IngestedArticle]:
        queries = self.config.get("queries") or DEFAULT_QUERIES
        lookback_days = int(self.config.get("lookback_days", 30))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).date().isoformat()

        api_token = self.config.get("api_token")
        headers = {}
        if api_token and not api_token.startswith("PASTE_"):
            headers["Authorization"] = f"Token {api_token}"

        for q in queries:
            params = {
                "q": q,
                "type": "o",  # opinions
                "filed_after": cutoff,
                "order_by": "dateFiled desc",
            }
            try:
                r = httpx.get(COURTLISTENER_URL, params=params, headers=headers, timeout=30.0)
                if r.status_code != 200:
                    continue
                data = r.json()
            except (httpx.HTTPError, ValueError):
                continue

            for a in data.get("results", []) or []:
                # CourtListener opinion search returns one record per case;
                # the URL points to the case page; we use the snippet field
                # for raw_text so Gemini can extract defendant/judge/sentence.
                case_url = a.get("absolute_url") or ""
                if case_url and not case_url.startswith("http"):
                    case_url = f"https://www.courtlistener.com{case_url}"
                if not case_url:
                    continue
                title = a.get("caseName") or a.get("caseNameShort") or ""
                snippet_list = a.get("snippet") or a.get("snippets") or []
                if isinstance(snippet_list, list):
                    snippet = "\n".join(s for s in snippet_list if s)
                else:
                    snippet = str(snippet_list)
                court = a.get("court") or "Federal Court"
                judge = a.get("judge") or ""
                date_filed = a.get("dateFiled") or ""

                # Build a richer raw_text the LLM can extract from
                raw_text = "\n".join(filter(None, [
                    f"Case: {title}",
                    f"Court: {court}",
                    f"Judge: {judge}" if judge else "",
                    f"Date filed: {date_filed}" if date_filed else "",
                    snippet,
                ]))

                pub_at = None
                if date_filed:
                    try:
                        pub_at = datetime.fromisoformat(date_filed).replace(tzinfo=timezone.utc)
                    except ValueError:
                        pub_at = None

                yield IngestedArticle(
                    url=case_url,
                    title=title or None,
                    published_at=pub_at,
                    raw_text=raw_text,
                    source_name=court or "CourtListener",
                    source_type="court_records",
                )
