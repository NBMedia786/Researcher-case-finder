from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from uuid import UUID as UUID_T
from app.db import get_db
from app.models import Case, Article
from app.auth.dependencies import current_user
from app.schemas.case import CaseListResponse, CaseListItem, CaseDetail, CaseArticle, CaseUpdate

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


@router.get("/{case_id}", response_model=CaseDetail)
def get_case(case_id: UUID_T, db: Session = Depends(get_db), user=Depends(current_user)):
    c = db.query(Case).filter(Case.id == case_id).one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="case not found")
    arts = db.query(Article).filter(Article.case_id == case_id).all()
    base = CaseListItem.model_validate(c).model_dump()
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
