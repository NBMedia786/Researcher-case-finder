import threading
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db, SessionLocal
from app.models import Source
from app.auth.dependencies import admin_required
from app.schemas.source import SourceItem, SourceList, SourceToggle
from app.workers.pipeline import process_article
from app.workers.tasks import _build_source

router = APIRouter()


@router.get("", response_model=SourceList)
def list_sources(db: Session = Depends(get_db), user=Depends(admin_required)):
    sources = db.query(Source).order_by(Source.name).all()
    return SourceList(
        items=[SourceItem.model_validate(s) for s in sources],
        total=len(sources),
    )


@router.patch("/{source_id}", response_model=SourceItem)
def toggle_source(
    source_id: UUID,
    body: SourceToggle,
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    s = db.query(Source).filter(Source.id == source_id).one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="source not found")
    s.is_active = body.is_active
    db.commit()
    db.refresh(s)
    return SourceItem.model_validate(s)


def _ingest_one_source(source_id_str: str) -> None:
    """Background worker: fetch + extract a single source. No Celery needed."""
    db = SessionLocal()
    try:
        source = (
            db.query(Source).filter(Source.id == source_id_str, Source.is_active).one_or_none()
        )
        if source is None:
            return
        src = _build_source(source)
        if src is None:
            return
        fetched = 0
        extracted = 0
        try:
            for ia in src.fetch():
                fetched += 1
                try:
                    result = process_article(db, ia)
                    if not result.get("skipped"):
                        extracted += 1
                except Exception:
                    db.rollback()
                    continue
            source.last_run_at = datetime.now(timezone.utc)
            source.last_success_at = datetime.now(timezone.utc)
            source.items_fetched_24h = fetched
            source.items_extracted_24h = extracted
            source.consecutive_failures = 0
            db.commit()
        except Exception:
            source.last_run_at = datetime.now(timezone.utc)
            source.consecutive_failures = (source.consecutive_failures or 0) + 1
            db.commit()
    finally:
        db.close()


@router.post("/{source_id}/run")
def run_source_now(
    source_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    s = db.query(Source).filter(Source.id == source_id).one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="source not found")
    # Background thread (no Celery dependency)
    thread = threading.Thread(target=_ingest_one_source, args=(str(s.id),), daemon=True)
    thread.start()
    return {"queued": True, "source_id": str(s.id)}
