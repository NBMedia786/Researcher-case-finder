import re
import threading
import uuid as uuid_lib
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db import get_db, SessionLocal
from app.models import Source, PipelineRun, Topic, User
from app.auth.dependencies import current_user
from app.extraction.prompts import DEFAULT_TOPIC_CRITERIA
from app.workers.pipeline import process_article
from app.workers.tasks import _build_source

router = APIRouter()


# Researchers naturally write variant lists like
#   "Body Concealment, Concealment of Corpse or Body Disposal"
# We split that into 3 separate queries so each variant gets its own
# search-API call (instead of one impossible long-phrase query that
# returns nothing). Separators: comma, newline, or the word "or"
# surrounded by whitespace (case-insensitive). Bare "or" inside a word
# like "orange" or "northern" is NOT split — we require whitespace on
# both sides.
_QUERY_SPLIT_RE = re.compile(r"\s*,\s*|\s*\n\s*|\s+or\s+", re.IGNORECASE)


def _split_queries(text: str) -> list[str]:
    """Split a search string into individual query fragments.

    "Body Concealment or Body Disposal"  -> ["Body Concealment", "Body Disposal"]
    "A, B, C"                            -> ["A", "B", "C"]
    "kidnapping california"              -> ["kidnapping california"]
    """
    parts = [p.strip() for p in _QUERY_SPLIT_RE.split(text or "")]
    return [p for p in parts if p]


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


def _is_cancel_requested(db: Session, run_id: str) -> bool:
    """Re-read the run row from the DB and check if the user has requested
    cancellation. The cancel endpoint flips status from 'running' to
    'cancelling'; here we honor that signal."""
    try:
        current_status = (
            db.query(PipelineRun.status)
            .filter(PipelineRun.id == run_id)
            .scalar()
        )
        return current_status == "cancelling"
    except Exception:
        # If we can't read the DB momentarily, assume not cancelled and
        # let the next iteration try again.
        return False


def _run_pipeline_in_thread(run_id: str, user_id: str) -> None:
    """Long-running pipeline body. Runs in a background thread with its own
    DB session. Updates the PipelineRun row as it progresses.

    Honors cancellation: between each source and every 5 articles, we
    re-read the run row; if the user flipped status to 'cancelling', we
    stop gracefully and mark the run 'cancelled' with whatever partial
    counts we accumulated.
    """
    db = SessionLocal()
    cancelled = False
    try:
        run = db.query(PipelineRun).filter(PipelineRun.id == run_id).one()
        # Active topic drives queries + LLM criteria + recency filter.
        topic = db.query(Topic).filter(Topic.is_active.is_(True)).one_or_none()
        sources = db.query(Source).filter(Source.is_active).all()
        sources.sort(key=lambda s: (_SOURCE_PRIORITY.get(s.name, 50), s.name))

        for source in sources:
            # Check before starting each source — cheapest cancel point.
            if _is_cancel_requested(db, run_id):
                cancelled = True
                break
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
                    # Commit progress every 5 articles so the UI can see it,
                    # and check for cancellation at the same cadence.
                    if per["fetched"] % 5 == 0:
                        db.commit()
                        if _is_cancel_requested(db, run_id):
                            cancelled = True
                            break  # leave the per-source fetch loop
                if cancelled:
                    # Don't mark source as fully successful — we stopped early.
                    source.items_fetched_24h = per["fetched"]
                    source.items_extracted_24h = per["extracted"]
                else:
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
            if cancelled:
                break  # leave the outer source loop too

        run.status = "cancelled" if cancelled else "completed"
        run.current_source = None
        run.finished_at = datetime.now(timezone.utc)
        if cancelled:
            run.errors = list(run.errors or []) + ["cancelled by user"]
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


class RunSearchRequest(BaseModel):
    search_text: str
    recency_days: int | None = None
    # When true (default), the user's freeform text is rewritten by Gemini
    # into a list of search-API-friendly query variants. Setting false
    # uses only the manual comma/'or' splitter.
    smart_expand: bool = True


@router.post("/run-search")
def run_search(
    body: RunSearchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Google-style search-and-run: take keyword text, create or reuse a
    Topic with that name + query, activate it, and start the pipeline.

    The search text becomes both the topic name (shown as a chip on each
    case row) and the list of query strings sent to every source. Comma-
    or "or"-separated variants are split into individual queries so each
    one gets its own search-API call. Extraction criteria defaults to the
    broad homicide-sentencing template so cases that surface for the
    keywords are still vetted by the LLM."""
    text = (body.search_text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="search_text required")
    if len(text) > 512:
        raise HTTPException(status_code=400, detail="search_text too long (max 512)")

    # Smart expansion: hand the user's freeform text to Gemini for a
    # short list of search-API-friendly variants. On any LLM failure the
    # expander falls back to the manual splitter so the search still
    # runs. We always keep the user's original input as the topic name —
    # short and stable for the case chip — and store the expanded list
    # as the queries to send out.
    expansion_model: str | None = None
    if body.smart_expand:
        from app.extraction.query_expander import expand_query
        queries, expansion_model = expand_query(text)
    else:
        queries = _split_queries(text)
    if not queries:
        raise HTTPException(status_code=400, detail="search_text has no usable terms")
    # Topic name = the researcher's original input (trimmed). Stable
    # display label even when expansion produces 6 variants.
    canonical_name = text

    # Reuse an existing topic with the same name (case-insensitive)
    # instead of piling up duplicates each time the researcher re-runs.
    topic = (
        db.query(Topic)
        .filter(func.lower(Topic.name) == canonical_name.lower())
        .one_or_none()
    )
    if topic is None:
        topic = Topic(
            name=canonical_name,
            queries=queries,
            extraction_criteria=DEFAULT_TOPIC_CRITERIA,
            recency_days=body.recency_days or 14,
            is_active=False,
            is_default=False,
        )
        db.add(topic)
        db.flush()
    else:
        # Keep the queries in sync with the latest text typed (researchers
        # may refine wording across runs of the "same" search).
        if list(topic.queries or []) != queries:
            topic.queries = queries
        if body.recency_days:
            topic.recency_days = body.recency_days

    # Activate this topic (and only this one). Partial unique index on
    # is_active=true forces us to clear others first.
    db.query(Topic).filter(
        Topic.is_active.is_(True), Topic.id != topic.id
    ).update({"is_active": False}, synchronize_session=False)
    topic.is_active = True
    db.commit()
    db.refresh(topic)

    # Re-attach to an already-running pipeline rather than spawning a second.
    existing_run = (
        db.query(PipelineRun)
        .filter(PipelineRun.status == "running")
        .order_by(PipelineRun.started_at.desc())
        .first()
    )
    if existing_run is not None:
        return {
            "run_id": str(existing_run.id),
            "status": existing_run.status,
            "already_running": True,
            "topic_id": str(topic.id),
            "topic_name": topic.name,
            "queries": list(topic.queries or []),
            "expanded_by": expansion_model,
        }

    run = PipelineRun(status="running", started_by=user.id)
    db.add(run)
    db.commit()
    db.refresh(run)

    thread = threading.Thread(
        target=_run_pipeline_in_thread,
        args=(str(run.id), str(user.id)),
        daemon=True,
    )
    thread.start()
    return {
        "run_id": str(run.id),
        "status": "running",
        "already_running": False,
        "topic_id": str(topic.id),
        "topic_name": topic.name,
        "queries": list(topic.queries or []),
        "expanded_by": expansion_model,
    }


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


@router.post("/cancel-pipeline")
def cancel_pipeline(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """Request cancellation of the currently-running pipeline.

    Flips status from 'running' -> 'cancelling'. The background worker
    notices on its next 5-article checkpoint and exits gracefully,
    flipping status to 'cancelled' and preserving partial counts.
    No-op if no pipeline is running.
    """
    run = (
        db.query(PipelineRun)
        .filter(PipelineRun.status.in_(["running", "cancelling"]))
        .order_by(PipelineRun.started_at.desc())
        .first()
    )
    if run is None:
        return {"cancelled": False, "reason": "no pipeline running"}
    if run.status == "cancelling":
        return {"cancelled": True, "run_id": str(run.id), "status": "cancelling", "already_requested": True}
    run.status = "cancelling"
    db.commit()
    return {"cancelled": True, "run_id": str(run.id), "status": "cancelling", "already_requested": False}
