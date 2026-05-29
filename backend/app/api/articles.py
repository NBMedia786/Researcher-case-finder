from datetime import date as date_cls, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, func, distinct
from sqlalchemy.orm import Session
from uuid import UUID as UUID_T

from app.db import get_db
from app.models import Article, Case, AuditLog, Topic
from app.auth.dependencies import current_user
from app.dedup.matcher import find_matching_case, normalize_name, merge_extracted_into_case
from app.scoring.score import compute_content_score
from app.schemas.article import (
    ArticleListItem,
    ArticleListResponse,
    ArticleStatusCounts,
    PromoteRequest,
    PromoteResponse,
)

router = APIRouter()


def _derive_rejection_reason(a: Article) -> Optional[str]:
    """Best-effort short reason for why an article didn't become a case."""
    if a.extraction_status == "failed":
        # Gemini call errored or returned malformed JSON.
        return (a.extraction_error or "extraction failed")[:240]
    if a.extraction_status != "no_match":
        return None
    # For no_match, the LLM's own summary explains why (e.g. "trial ongoing",
    # "foreign-language article", "future indictment, not a sentencing").
    data = a.extracted_json or {}
    if isinstance(data, dict):
        summary = data.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()[:240]
    # Otherwise fall back to whatever pipeline.py wrote (e.g. "event too old").
    return (a.extraction_error or "did not match sentencing criteria")[:240]


def _to_list_item(a: Article, topic_names: dict) -> ArticleListItem:
    data = a.extracted_json or {}
    if not isinstance(data, dict):
        data = {}
    return ArticleListItem(
        id=a.id,
        url=a.url,
        title=a.title,
        source_name=a.source_name,
        source_type=a.source_type,
        published_at=a.published_at,
        created_at=a.created_at,
        extraction_status=a.extraction_status,
        extraction_error=a.extraction_error,
        case_id=a.case_id,
        topic_id=a.topic_id,
        topic_name=topic_names.get(a.topic_id),
        rejection_reason=_derive_rejection_reason(a),
        extracted_defendant_name=data.get("defendant_name"),
        extracted_state=data.get("state"),
        extracted_sentencing_date=data.get("sentencing_date"),
    )


@router.get("", response_model=ArticleListResponse)
def list_articles(
    db: Session = Depends(get_db),
    user=Depends(current_user),
    status: Optional[str] = None,
    source: Optional[str] = None,
    q: Optional[str] = None,
    since: Optional[date_cls] = None,  # inclusive lower bound on created_at
    until: Optional[date_cls] = None,  # inclusive upper bound on created_at
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    """List articles in the pool with optional filtering by status, source,
    keyword, and date range. The "Raw articles" tab in the inbox uses this."""
    qry = db.query(Article)
    if status and status != "all":
        qry = qry.filter(Article.extraction_status == status)
    if source:
        qry = qry.filter(Article.source_name == source)
    if since is not None:
        qry = qry.filter(Article.created_at >= datetime.combine(since, datetime.min.time()))
    if until is not None:
        qry = qry.filter(Article.created_at <= datetime.combine(until, datetime.max.time()))
    if q:
        like = f"%{q.lower()}%"
        qry = qry.filter(or_(
            Article.title.ilike(like),
            Article.raw_text.ilike(like),
        ))
    total = qry.count()
    items = (
        qry.order_by(Article.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    # Bulk-lookup topic names so each row can show its search-keyword chip
    # without doing one query per article.
    topic_ids = {a.topic_id for a in items if a.topic_id is not None}
    topic_names: dict = {}
    if topic_ids:
        for t in db.query(Topic).filter(Topic.id.in_(topic_ids)).all():
            topic_names[t.id] = t.name
    return ArticleListResponse(
        items=[_to_list_item(a, topic_names) for a in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/_status_counts", response_model=ArticleStatusCounts)
def article_status_counts(db: Session = Depends(get_db), user=Depends(current_user)):
    """Counts per extraction_status — drives the tab badges in the UI."""
    rows = (
        db.query(Article.extraction_status, func.count(Article.id))
        .group_by(Article.extraction_status)
        .all()
    )
    out = {"pending": 0, "extracted": 0, "no_match": 0, "failed": 0}
    for s, n in rows:
        if s in out:
            out[s] = n
    out["all"] = sum(out.values())
    return ArticleStatusCounts(**out)


@router.get("/_sources")
def article_sources(db: Session = Depends(get_db), user=Depends(current_user)):
    """Distinct source_names in the article pool, ordered by frequency.
    Used to populate the Source dropdown filter in the Raw-Articles tab."""
    rows = (
        db.query(Article.source_name, func.count(Article.id).label("n"))
        .group_by(Article.source_name)
        .order_by(func.count(Article.id).desc())
        .all()
    )
    return {"sources": [{"name": name, "count": n} for name, n in rows]}


@router.post("/{article_id}/promote", response_model=PromoteResponse)
def promote_article(
    article_id: UUID_T,
    body: PromoteRequest,
    db: Session = Depends(get_db),
    user=Depends(current_user),
):
    """Manually convert an article into a Case — used when Gemini wrongly
    rejected it, or when the researcher wants to capture an article that
    didn't make it through automatic extraction.

    Uses extracted_json fields where available, with overrides supplied in
    the request body. defendant_name + state + sentencing_date are
    required (in body or extracted_json) to satisfy NOT NULL constraints.
    """
    article = db.query(Article).filter(Article.id == article_id).one_or_none()
    if article is None:
        raise HTTPException(status_code=404, detail="article not found")

    data = article.extracted_json if isinstance(article.extracted_json, dict) else {}

    defendant = (body.defendant_name or data.get("defendant_name") or "").strip()
    state = ((body.state or data.get("state") or "").strip().upper())[:2]
    sentencing_date_raw = body.sentencing_date or data.get("sentencing_date")
    sentencing_date = None
    if sentencing_date_raw:
        try:
            sentencing_date = datetime.strptime(sentencing_date_raw, "%Y-%m-%d").date()
        except ValueError:
            sentencing_date = None
    # Fall back to article's published date for the sentencing if unknown —
    # researcher can correct via the case detail view afterward.
    if sentencing_date is None and article.published_at is not None:
        sentencing_date = article.published_at.date()

    missing = [
        n for n, v in (("defendant_name", defendant), ("state", state), ("sentencing_date", sentencing_date))
        if not v
    ]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"cannot promote — missing required fields: {', '.join(missing)}",
        )

    # Reuse an existing case if the same defendant+state+date matches.
    match = find_matching_case(db, defendant, sentencing_date, state)
    reused_existing = False
    created = False
    if match is not None:
        case = match
        merge_extracted_into_case(case, data)
        case.content_score = compute_content_score(data)
        reused_existing = True
    else:
        case = Case(
            defendant_name=defendant,
            defendant_name_normalized=normalize_name(defendant),
            defendant_age=data.get("defendant_age"),
            defendant_hometown=data.get("defendant_hometown"),
            victims=data.get("victims") or [],
            charges=data.get("charges") or [],
            sentence_text=data.get("sentence_text"),
            sentence_years=data.get("sentence_years"),
            sentence_type=data.get("sentence_type"),
            sentencing_date=sentencing_date,
            court_name=data.get("court_name"),
            county=data.get("county"),
            state=state,
            docket_number=data.get("docket_number"),
            judge_name=data.get("judge_name"),
            prosecuting_office=data.get("prosecuting_office"),
            investigating_agency=data.get("investigating_agency"),
            summary=data.get("summary"),
            status="new",
            notes=body.notes,
        )
        case.content_score = compute_content_score(data)
        db.add(case)
        db.flush()
        created = True

    # Re-attach the article to the case + mark it as extracted so it
    # disappears from the "no_match"/"failed" tab.
    article.case_id = case.id
    article.extraction_status = "extracted"

    db.add(AuditLog(
        user_id=getattr(user, "id", None),
        action="article_promoted_to_case",
        entity_type="article",
        entity_id=article.id,
        extra={
            "case_id": str(case.id),
            "created": created,
            "reused_existing": reused_existing,
            "defendant_name": defendant,
        },
    ))
    db.commit()
    return PromoteResponse(case_id=case.id, created=created, reused_existing=reused_existing)
