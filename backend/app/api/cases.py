from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from uuid import UUID as UUID_T, UUID
from pydantic import BaseModel as _BM
from app.db import get_db
from app.models import Case, Article, AuditLog, Topic
from app.auth.dependencies import current_user
from app.schemas.case import CaseListResponse, CaseListItem, CaseDetail, CaseArticle, CaseUpdate


def _build_list_item(case: Case, topic_name_lookup: dict) -> CaseListItem:
    """Serialize a Case with its joined topic_name."""
    base = {
        c.name: getattr(case, c.name)
        for c in Case.__table__.columns
        if c.name in CaseListItem.model_fields and c.name != "topic_name"
    }
    base["topic_name"] = topic_name_lookup.get(case.topic_id)
    return CaseListItem.model_validate(base)


def _as_uuid(val) -> UUID | None:
    """Coerce a string or UUID to a UUID object, or return None."""
    if val is None:
        return None
    if isinstance(val, UUID):
        return val
    try:
        return UUID(str(val))
    except (ValueError, AttributeError):
        return None

router = APIRouter()


@router.get("", response_model=CaseListResponse)
def list_cases(
    db: Session = Depends(get_db),
    user=Depends(current_user),
    status: Optional[str] = None,
    state: Optional[str] = None,
    min_score: Optional[int] = None,
    q: Optional[str] = None,
    assigned_to: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    qry = db.query(Case)
    if status:
        qry = qry.filter(Case.status == status)
    if state:
        qry = qry.filter(Case.state == state.upper())
    if min_score:
        qry = qry.filter(Case.content_score >= min_score)
    if assigned_to:
        if assigned_to == "__unassigned__":
            qry = qry.filter(Case.assigned_to.is_(None))
        else:
            qry = qry.filter(Case.assigned_to == assigned_to)
    if q:
        like = f"%{q.lower()}%"
        qry = qry.filter(or_(
            Case.defendant_name.ilike(like),
            Case.summary.ilike(like),
        ))
    total = qry.count()
    items = (qry
             .order_by(Case.content_score.desc(), Case.sentencing_date.desc())
             .offset((page - 1) * page_size)
             .limit(page_size)
             .all())
    # Bulk-lookup topic names for this page (avoids per-row queries).
    topic_ids = {c.topic_id for c in items if c.topic_id is not None}
    topic_name_lookup: dict = {}
    if topic_ids:
        for t in db.query(Topic).filter(Topic.id.in_(topic_ids)).all():
            topic_name_lookup[t.id] = t.name
    return CaseListResponse(
        items=[_build_list_item(c, topic_name_lookup) for c in items],
        total=total, page=page, page_size=page_size,
    )


TEAM_MEMBERS = ["Gagandeep", "Rudransh", "Piyush", "Cyrus", "Shivanshi", "Vandana"]


@router.get("/_status_counts")
def status_counts(db: Session = Depends(get_db), user=Depends(current_user)):
    """Return a count of cases per status + per-assignee — used by the inbox tabs."""
    from sqlalchemy import func
    rows = (
        db.query(Case.status, func.count(Case.id))
        .group_by(Case.status)
        .all()
    )
    out = {s: 0 for s in (
        "new", "reviewing", "approved", "rejected",
        "foia_filed", "records_received", "archived",
    )}
    for s, n in rows:
        out[s] = n
    out["all"] = sum(out.values())

    by_assignee = {m: 0 for m in TEAM_MEMBERS}
    by_assignee["__unassigned__"] = 0
    assignee_rows = (
        db.query(Case.assigned_to, func.count(Case.id))
        .group_by(Case.assigned_to)
        .all()
    )
    for name, n in assignee_rows:
        if name is None:
            by_assignee["__unassigned__"] = n
        elif name in by_assignee:
            by_assignee[name] = n
    out["by_assignee"] = by_assignee
    return out


@router.get("/{case_id}", response_model=CaseDetail)
def get_case(case_id: UUID_T, db: Session = Depends(get_db), user=Depends(current_user)):
    c = db.query(Case).filter(Case.id == case_id).one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="case not found")
    arts = db.query(Article).filter(Article.case_id == case_id).all()
    topic_name = None
    if c.topic_id is not None:
        t = db.query(Topic).filter(Topic.id == c.topic_id).one_or_none()
        topic_name = t.name if t else None
    base = _build_list_item(c, {c.topic_id: topic_name} if c.topic_id else {}).model_dump()
    return CaseDetail(
        **base,
        victims=c.victims or [],
        charges=c.charges or [],
        docket_number=c.docket_number,
        judge_name=c.judge_name,
        court_name=c.court_name,
        prosecuting_office=c.prosecuting_office,
        investigating_agency=c.investigating_agency,
        sentence_years=c.sentence_years,
        notes=c.notes,
        articles=[CaseArticle.model_validate(a) for a in arts],
    )


@router.patch("/{case_id}", response_model=CaseDetail)
def update_case(case_id: UUID_T, body: CaseUpdate,
                db: Session = Depends(get_db), user=Depends(current_user)):
    c = db.query(Case).filter(Case.id == case_id).one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="case not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "state" and value:
            value = value.upper()[:2]
        setattr(c, field, value)
    db.commit()
    db.refresh(c)
    return get_case(case_id, db, user)


class TransitionRequest(_BM):
    action: str
    note: str | None = None


ACTION_MAP = {
    "approve": "approved",
    "reject": "rejected",
    "needs_info": "reviewing",
    "mark_foia_filed": "foia_filed",
    "mark_records_received": "records_received",
    "archive": "archived",
}


@router.post("/{case_id}/transition", response_model=CaseDetail)
def transition_case(case_id: UUID_T, body: TransitionRequest,
                    db: Session = Depends(get_db), user=Depends(current_user)):
    new_status = ACTION_MAP.get(body.action)
    if new_status is None:
        raise HTTPException(status_code=400, detail="invalid action")
    c = db.query(Case).filter(Case.id == case_id).one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="case not found")
    c.status = new_status
    c.reviewed_by = _as_uuid(user.id)
    c.reviewed_at = datetime.now(timezone.utc)
    if body.note:
        c.notes = (c.notes + "\n" if c.notes else "") + body.note
    db.add(AuditLog(
        user_id=_as_uuid(user.id), action=f"case_{body.action}",
        entity_type="case", entity_id=case_id,
        extra={"new_status": new_status, "note": body.note},
    ))
    db.commit()
    db.refresh(c)
    return get_case(case_id, db, user)
