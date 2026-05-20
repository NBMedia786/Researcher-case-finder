from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Source
from app.auth.dependencies import admin_required
from app.schemas.source import SourceItem, SourceList, SourceToggle
from app.workers.tasks import ingest_source

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


@router.post("/{source_id}/run")
def run_source_now(
    source_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    s = db.query(Source).filter(Source.id == source_id).one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="source not found")
    ingest_source.delay(str(s.id))
    return {"queued": True, "source_id": str(s.id)}
