import threading
import uuid as uuid_lib
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db, SessionLocal
from app.models import Source, PipelineRun, Topic, User
from app.auth.dependencies import current_user
from app.workers.pipeline import process_article
from app.workers.tasks import _build_source

router = APIRouter()


_SOURCE_PRIORITY = {
    # Run high-signal web-search APIs FIRST — they return small numbers of
    # high-quality results curated by search engines, so researchers see
    # cases in the inbox within minutes of clicking Run pipeline.
    "tavily": 1,
    "serpapi": 2,
    # News-search APIs (medium volume, medium speed).
    "newsapi": 3,
    "newsdata": 4,
    "gnews": 5,
    "mediastack": 6,
    # Court records + curated RSS feeds (fast, narrow scope).
    "courtlistener": 7,
    "marshall_project": 8,
    "prnewswire": 9,
    "doj": 10,
    # GDELT last — it's the broadest (potentially 1,500+ articles) AND
    # the slowest. Running it last means we already have the easy wins
    # in the inbox if GDELT stalls out or hits rate limits.
    "gdelt": 99,
}


def _run_pipeline_in_thread(run_id: str, user_id: str) -> None:
    """Long-running pipeline body. Runs in a background thread with its own
    DB session. Updates the PipelineRun row as it progresses."""
    db = SessionLocal()
    try:
        run = db.query(PipelineRun).filter(PipelineRun.id == run_id).one()
        # Active topic drives queries + LLM criteria + recency filter.
        topic = db.query(Topic).filter(Topic.is_active.is_(True)).one_or_none()
        sources = db.query(Source).filter(Source.is_active).all()
        sources.sort(key=lambda s: (_SOURCE_PRIORITY.get(s.name, 50), s.name))

        for source in sources:
            run.current_source = source.name
            per = {"name": source.name, "fetched": 0, "extracted": 0, "new_cases": 0}
            # Mark the source as started right away so partial counts are
            # recoverable even if the pipeline is killed mid-run.
            source.last_run_at = datetime.now(timezone.utc)
            source.items_fetched_24h = 0
            source.items_extracted_24h = 0
            db.commit()
            src = _build_source(source, topic=topic)
            if src is None:
                run.errors = list(run.errors) + [f"{source.name}: no handler"]
                run.per_source = list(run.per_source) + [per]
                db.commit()
                continue
            try:
                for ia in src.fetch():
                    per["fetched"] += 1
                    run.total_fetched += 1
                    try:
                        result = process_article(db, ia, topic=topic)
                        if not result.get("skipped"):
                            per["extracted"] += 1
                            run.total_extracted += 1
                        if result.get("created_case"):
                            per["new_cases"] += 1
                            run.total_new_cases += 1
                    except Exception as e:
                        db.rollback()
                        run.errors = list(run.errors) + [
                            f"{source.name}: {type(e).__name__}: {str(e)[:160]}"
                        ]
                    # Update source counters incrementally so the Sources page
                    # reflects live progress even mid-run.
                    source.items_fetched_24h = per["fetched"]
                    source.items_extracted_24h = per["extracted"]
                    # Commit progress every 5 articles so the UI can see it.
                    if per["fetched"] % 5 == 0:
                        db.commit()
                # Source completed without a fatal fetch error — mark success.
                source.last_run_at = datetime.now(timezone.utc)
                source.last_success_at = datetime.now(timezone.utc)
                source.items_fetched_24h = per["fetched"]
                source.items_extracted_24h = per["extracted"]
                source.consecutive_failures = 0
            except Exception as e:
                run.errors = list(run.errors) + [
                    f"{source.name}: fetch failed: {type(e).__name__}: {str(e)[:160]}"
                ]
                source.last_run_at = datetime.now(timezone.utc)
                source.consecutive_failures = (source.consecutive_failures or 0) + 1
            run.per_source = list(run.per_source) + [per]
            db.commit()

        run.status = "completed"
        run.current_source = None
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        try:
            run = db.query(PipelineRun).filter(PipelineRun.id == run_id).one_or_none()
            if run:
                run.status = "failed"
                run.finished_at = datetime.now(timezone.utc)
                run.errors = list(run.errors or []) + [f"fatal: {type(e).__name__}: {str(e)[:200]}"]
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


@router.post("/run-pipeline")
def start_pipeline(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Kick off a pipeline run in a background thread. Returns the run_id
    immediately. Use GET /api/admin/pipeline-status to track progress."""

    # If a run is already in progress, return it instead of starting another
    existing = (
        db.query(PipelineRun)
        .filter(PipelineRun.status == "running")
        .order_by(PipelineRun.started_at.desc())
        .first()
    )
    if existing is not None:
        return {
            "run_id": str(existing.id),
            "status": existing.status,
            "already_running": True,
        }

    run = PipelineRun(status="running", started_by=user.id)
    db.add(run)
    db.commit()
    db.refresh(run)

    run_id = str(run.id)
    user_id = str(user.id)
    thread = threading.Thread(
        target=_run_pipeline_in_thread, args=(run_id, user_id), daemon=True
    )
    thread.start()

    return {"run_id": run_id, "status": "running", "already_running": False}


@router.get("/pipeline-status")
def pipeline_status(db: Session = Depends(get_db), user=Depends(current_user)):
    """Return the latest pipeline run row. Frontend polls this every 3s."""
    run = (
        db.query(PipelineRun)
        .order_by(PipelineRun.started_at.desc())
        .first()
    )
    if run is None:
        return {"run": None}
    return {
        "run": {
            "id": str(run.id),
            "status": run.status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "current_source": run.current_source,
            "total_fetched": run.total_fetched,
            "total_extracted": run.total_extracted,
            "total_new_cases": run.total_new_cases,
            "per_source": run.per_source,
            "errors": run.errors,
        }
    }
