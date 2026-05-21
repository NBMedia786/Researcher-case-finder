import threading
import uuid as uuid_lib
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db, SessionLocal
from app.models import Source, PipelineRun, User
from app.auth.dependencies import admin_required
from app.workers.pipeline import process_article
from app.workers.tasks import _build_source

router = APIRouter()


def _run_pipeline_in_thread(run_id: str, user_id: str) -> None:
    """Long-running pipeline body. Runs in a background thread with its own
    DB session. Updates the PipelineRun row as it progresses."""
    db = SessionLocal()
    try:
        run = db.query(PipelineRun).filter(PipelineRun.id == run_id).one()
        sources = db.query(Source).filter(Source.is_active).order_by(Source.name).all()

        for source in sources:
            run.current_source = source.name
            per = {"name": source.name, "fetched": 0, "extracted": 0, "new_cases": 0}
            db.commit()
            src = _build_source(source)
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
                        result = process_article(db, ia)
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
                    # Commit progress every 5 articles so the UI can see it.
                    if per["fetched"] % 5 == 0:
                        db.commit()
            except Exception as e:
                run.errors = list(run.errors) + [
                    f"{source.name}: fetch failed: {type(e).__name__}: {str(e)[:160]}"
                ]
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
    user: User = Depends(admin_required),
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
def pipeline_status(db: Session = Depends(get_db), admin=Depends(admin_required)):
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
