from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Source
from app.auth.dependencies import admin_required
from app.workers.pipeline import process_article
from app.workers.tasks import _build_source

router = APIRouter()


@router.post("/run-pipeline")
def run_pipeline_sync(db: Session = Depends(get_db), admin=Depends(admin_required)):
    """Run the ingestion pipeline synchronously (no Celery/Redis required).

    Iterates all active sources, fetches articles, extracts cases via LLM,
    and saves to the database. Used for local testing / manual triggers.
    """
    sources = db.query(Source).filter(Source.is_active).order_by(Source.name).all()
    summary = {
        "sources_used": [],
        "total_fetched": 0,
        "total_extracted": 0,
        "total_new_cases": 0,
        "errors": [],
    }
    for source in sources:
        src = _build_source(source)
        if src is None:
            summary["errors"].append(f"{source.name}: no handler")
            continue
        per_source = {"name": source.name, "fetched": 0, "extracted": 0, "new_cases": 0}
        try:
            for ia in src.fetch():
                per_source["fetched"] += 1
                try:
                    result = process_article(db, ia)
                    if not result.get("skipped"):
                        per_source["extracted"] += 1
                    if result.get("created_case"):
                        per_source["new_cases"] += 1
                except Exception as e:
                    db.rollback()
                    summary["errors"].append(f"{source.name}: {type(e).__name__}: {str(e)[:120]}")
                    continue
        except Exception as e:
            summary["errors"].append(f"{source.name}: fetch failed: {type(e).__name__}: {str(e)[:120]}")
        summary["sources_used"].append(per_source)
        summary["total_fetched"] += per_source["fetched"]
        summary["total_extracted"] += per_source["extracted"]
        summary["total_new_cases"] += per_source["new_cases"]
    return summary
