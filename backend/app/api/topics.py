"""Topics CRUD — saved search profiles that drive the pipeline.

Per the product decision, ALL logged-in researchers can create / edit /
activate topics (not just admins). Only the default topic ("Homicide
Sentencings") cannot be deleted — it's the fallback target for the
cases.topic_id server-default.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.dependencies import current_user
from app.db import get_db
from app.models import Case, Topic
from app.schemas.topic import TopicCreate, TopicItem, TopicList, TopicUpdate

router = APIRouter()


def _serialize(t: Topic, db: Session) -> TopicItem:
    count = (
        db.query(func.count(Case.id)).filter(Case.topic_id == t.id).scalar() or 0
    )
    base = TopicItem.model_validate(t).model_dump()
    base["case_count"] = count
    return TopicItem(**base)


@router.get("", response_model=TopicList)
def list_topics(db: Session = Depends(get_db), _user=Depends(current_user)):
    rows = db.query(Topic).order_by(Topic.is_active.desc(), Topic.name).all()
    items = [_serialize(t, db) for t in rows]
    return TopicList(items=items, total=len(items))


@router.get("/active", response_model=TopicItem)
def get_active_topic(db: Session = Depends(get_db), _user=Depends(current_user)):
    t = db.query(Topic).filter(Topic.is_active.is_(True)).one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail="no active topic")
    return _serialize(t, db)


@router.post("", response_model=TopicItem, status_code=201)
def create_topic(
    body: TopicCreate,
    db: Session = Depends(get_db),
    _user=Depends(current_user),
):
    if db.query(Topic).filter(Topic.name == body.name).first():
        raise HTTPException(status_code=409, detail="topic name already exists")
    t = Topic(
        name=body.name,
        queries=body.queries,
        extraction_criteria=body.extraction_criteria,
        recency_days=body.recency_days,
        is_active=False,
        is_default=False,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _serialize(t, db)


@router.patch("/{topic_id}", response_model=TopicItem)
def update_topic(
    topic_id: UUID,
    body: TopicUpdate,
    db: Session = Depends(get_db),
    _user=Depends(current_user),
):
    t = db.query(Topic).filter(Topic.id == topic_id).one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail="topic not found")
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"] != t.name:
        if db.query(Topic).filter(Topic.name == data["name"]).first():
            raise HTTPException(status_code=409, detail="topic name already exists")
    for k, v in data.items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return _serialize(t, db)


@router.delete("/{topic_id}", status_code=204)
def delete_topic(
    topic_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(current_user),
):
    t = db.query(Topic).filter(Topic.id == topic_id).one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail="topic not found")
    if t.is_default:
        raise HTTPException(
            status_code=400, detail="cannot delete the default topic"
        )
    if t.is_active:
        raise HTTPException(
            status_code=400, detail="cannot delete the active topic — activate another first"
        )
    db.delete(t)
    db.commit()


@router.post("/{topic_id}/activate", response_model=TopicItem)
def activate_topic(
    topic_id: UUID,
    db: Session = Depends(get_db),
    _user=Depends(current_user),
):
    t = db.query(Topic).filter(Topic.id == topic_id).one_or_none()
    if t is None:
        raise HTTPException(status_code=404, detail="topic not found")
    # Deactivate everything else in a single statement, then activate this
    # one. The partial unique index allows multiple is_active=false rows
    # but only one is_active=true.
    db.query(Topic).filter(Topic.is_active.is_(True)).update(
        {"is_active": False}, synchronize_session=False
    )
    t.is_active = True
    db.commit()
    db.refresh(t)
    return _serialize(t, db)
