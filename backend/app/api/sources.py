import threading
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db, SessionLocal
from app.config import settings
from app.models import Source
from app.auth.dependencies import admin_required
from app.schemas.source import SourceItem, SourceList, SourceToggle, SourceConfigUpdate
from app.workers.pipeline import process_article
from app.workers.tasks import _build_source

router = APIRouter()


# Which config field each source uses for its credential, and the
# settings/.env fallback that _build_source consults if the DB column
# is empty. The admin UI uses this to drive the API Key column +
# edit form.
SOURCE_KEY_FIELDS: dict[str, tuple[str, str]] = {
    # name             -> (config_field,   settings_attr)
    "newsapi":         ("api_key",   "newsapi_key"),
    "mediastack":      ("api_key",   "mediastack_key"),
    "serpapi":         ("api_key",   "serpapi_key"),
    "tavily":          ("api_key",   "tavily_api_key"),
    "courtlistener":   ("api_token", "courtlistener_api_token"),
    "newsdata":        ("api_key",   "newsdata_api_key"),
    "gnews":           ("api_key",   "gnews_api_key"),
}


def _mask(value: str) -> str:
    """Mask all but the last 4 characters of a credential for display."""
    if not value:
        return ""
    value = str(value)
    if len(value) <= 4:
        return "•" * len(value)
    return "•" * (len(value) - 4) + value[-4:]


def _to_item(s: Source) -> SourceItem:
    """Build a SourceItem with the masked key preview + source attribution
    (whether the live key is from DB config or env fallback)."""
    item = SourceItem.model_validate(s)
    spec = SOURCE_KEY_FIELDS.get(s.name)
    if spec is None:
        return item
    field, env_attr = spec
    item.key_field = field
    cfg_val = (s.config or {}).get(field) or ""
    env_val = getattr(settings, env_attr, None) or ""
    # Anything starting with PASTE_ is the seed placeholder, not a real key.
    if isinstance(cfg_val, str) and cfg_val and not cfg_val.startswith("PASTE_"):
        item.key_preview = _mask(cfg_val)
        item.key_source = "config"
    elif isinstance(env_val, str) and env_val and not env_val.startswith("PASTE_"):
        item.key_preview = _mask(env_val)
        item.key_source = "env"
    else:
        item.key_preview = None
        item.key_source = None
    return item


@router.get("", response_model=SourceList)
def list_sources(db: Session = Depends(get_db), user=Depends(admin_required)):
    sources = db.query(Source).order_by(Source.name).all()
    return SourceList(
        items=[_to_item(s) for s in sources],
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
    return _to_item(s)


@router.patch("/{source_id}/config", response_model=SourceItem)
def update_source_config(
    source_id: UUID,
    body: SourceConfigUpdate,
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    """Admin-only: write/clear the credential field on a source's config.

    Sending the empty string clears the field (then the env-var fallback
    takes over at runtime). Sending a non-empty string overrides env.
    """
    s = db.query(Source).filter(Source.id == source_id).one_or_none()
    if s is None:
        raise HTTPException(status_code=404, detail="source not found")
    spec = SOURCE_KEY_FIELDS.get(s.name)
    if spec is None:
        raise HTTPException(
            status_code=400,
            detail=f"source '{s.name}' does not use an API key",
        )
    field, _ = spec
    new_value = body.api_key if field == "api_key" else body.api_token
    if new_value is None:
        raise HTTPException(status_code=400, detail=f"missing field: {field}")
    cfg = dict(s.config or {})
    cleaned = new_value.strip()
    if cleaned:
        cfg[field] = cleaned
    else:
        # Empty input clears the override so env-var fallback kicks back in.
        cfg.pop(field, None)
    s.config = cfg
    db.commit()
    db.refresh(s)
    return _to_item(s)


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
