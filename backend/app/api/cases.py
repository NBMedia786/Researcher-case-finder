from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.db import get_db
from app.models import Case
from app.auth.dependencies import current_user
from app.schemas.case import CaseListResponse, CaseListItem

router = APIRouter()


@router.get("", response_model=CaseListResponse)
def list_cases(
    db: Session = Depends(get_db),
    user=Depends(current_user),
    status: Optional[str] = None,
    state: Optional[str] = None,
    min_score: Optional[int] = None,
    q: Optional[str] = None,
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
    return CaseListResponse(
        items=[CaseListItem.model_validate(c) for c in items],
        total=total, page=page, page_size=page_size,
    )
