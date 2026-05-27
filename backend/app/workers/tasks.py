from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from app.workers.celery_app import celery_app
from app.workers.pipeline import process_article
from app.db import SessionLocal
from app.models import Source, Case
from app.sources.newsapi import NewsAPISource
from app.sources.doj import DOJSource
from app.sources.mediastack import MediaStackSource
from app.sources.gdelt import GdeltSource
from app.sources.serpapi import SerpAPISource
from app.sources.tavily import TavilySource
from app.sources.courtlistener import CourtListenerSource
from app.sources.marshall_project import MarshallProjectSource
from app.sources.prnewswire import PRNewswireSource
from app.sources.newsdata import NewsDataSource
from app.sources.gnews import GNewsSource
from app.config import settings
from app.notifications.slack import post_summary

SOURCE_REGISTRY = {
    "newsapi": NewsAPISource,
    "doj": DOJSource,
    "mediastack": MediaStackSource,
    "gdelt": GdeltSource,
    "serpapi": SerpAPISource,
    "tavily": TavilySource,
    "courtlistener": CourtListenerSource,
    "marshall_project": MarshallProjectSource,
    "prnewswire": PRNewswireSource,
    "newsdata": NewsDataSource,
    "gnews": GNewsSource,
}

def _build_source(row: Source, topic=None):
    """Build a source instance with API keys injected from settings, and
    optionally inject the active Topic's queries into the source config.

    For sources that take a `queries` config key, the topic's queries
    override the source's hardcoded DEFAULT_QUERIES. RSS sources (DOJ,
    Marshall Project, PR Newswire) ignore queries — they filter post-
    fetch by hardcoded keyword sets, so they'll keep behaving as a
    homicide filter regardless of topic for now (phase 2 will widen).
    """
    cls = SOURCE_REGISTRY.get(row.name)
    if cls is None:
        return None
    cfg = dict(row.config or {})
    # Inject API keys from settings
    if row.name == "newsapi":
        cfg["api_key"] = cfg.get("api_key") or settings.newsapi_key
    if row.name == "mediastack":
        cfg["api_key"] = cfg.get("api_key") or settings.mediastack_key
    if row.name == "serpapi":
        cfg["api_key"] = cfg.get("api_key") or settings.serpapi_key
    if row.name == "tavily":
        cfg["api_key"] = cfg.get("api_key") or settings.tavily_api_key
    if row.name == "courtlistener":
        cfg["api_token"] = cfg.get("api_token") or settings.courtlistener_api_token
    if row.name == "newsdata":
        cfg["api_key"] = cfg.get("api_key") or settings.newsdata_api_key
    if row.name == "gnews":
        cfg["api_key"] = cfg.get("api_key") or settings.gnews_api_key

    # Inject the active topic's plain-keyword queries. Each source's
    # fetch() already prefers config["queries"] over its DEFAULT_QUERIES.
    # GDELT and MediaStack do per-source syntax adaptation internally.
    if topic is not None and topic.queries:
        cfg["queries"] = list(topic.queries)

    return cls(config=cfg)

@celery_app.task(bind=True, max_retries=3)
def ingest_source(self, source_id: str):
    db = SessionLocal()
    try:
        row = db.query(Source).filter(Source.id == source_id, Source.is_active).one_or_none()
        if row is None:
            return {"skipped": True}
        src = _build_source(row)
        if src is None:
            return {"skipped": True, "reason": "no handler"}
        fetched, extracted = 0, 0
        for ia in src.fetch():
            fetched += 1
            try:
                process_article(db, ia)
                extracted += 1
            except Exception:
                db.rollback()
                continue
        row.items_fetched_24h = fetched
        row.items_extracted_24h = extracted
        row.last_run_at = datetime.now(timezone.utc)
        row.last_success_at = datetime.now(timezone.utc)
        row.consecutive_failures = 0
        db.commit()
        return {"fetched": fetched, "extracted": extracted}
    except Exception as e:
        try:
            row = db.query(Source).filter(Source.id == source_id).one_or_none()
            if row:
                row.consecutive_failures = (row.consecutive_failures or 0) + 1
                row.last_run_at = datetime.now(timezone.utc)
                db.commit()
        finally:
            db.rollback()
        raise self.retry(exc=e, countdown=60) from e
    finally:
        db.close()

@celery_app.task
def run_full_pipeline():
    db = SessionLocal()
    try:
        ids = [str(s.id) for s in db.query(Source).filter(Source.is_active).all()]
    finally:
        db.close()
    for sid in ids:
        ingest_source.delay(sid)
    return {"dispatched": len(ids)}

@celery_app.task
def run_light_pipeline():
    return run_full_pipeline()

@celery_app.task
def post_daily_summary():
    db = SessionLocal()
    try:
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        new_count = db.query(func.count(Case.id)).filter(Case.created_at >= since).scalar() or 0
        high = (db.query(func.count(Case.id))
                  .filter(Case.created_at >= since, Case.content_score >= 4).scalar() or 0)
    finally:
        db.close()
    base = settings.frontend_url
    post_summary(f"NB Research: {new_count} new cases overnight, {high} high-priority. {base}/inbox")
    return {"new": new_count, "high": high}
