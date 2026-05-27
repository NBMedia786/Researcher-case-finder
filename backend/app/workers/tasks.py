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
}

def _build_source(row: Source):
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
