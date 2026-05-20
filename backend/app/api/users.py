from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User
from app.auth.dependencies import admin_required
from app.schemas.user import UserItem, UserList, UserUpdate, VALID_ROLES

router = APIRouter()


@router.get("", response_model=UserList)
def list_users(db: Session = Depends(get_db), user=Depends(admin_required)):
    users = db.query(User).order_by(User.email).all()
    return UserList(
        items=[UserItem.model_validate(u) for u in users],
        total=len(users),
    )


@router.patch("/{user_id}", response_model=UserItem)
def update_user(
    user_id: UUID,
    body: UserUpdate,
    db: Session = Depends(get_db),
    user=Depends(admin_required),
):
    u = db.query(User).filter(User.id == user_id).one_or_none()
    if u is None:
        raise HTTPException(status_code=404, detail="user not found")
    data = body.model_dump(exclude_unset=True)
    if "role" in data and data["role"] not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"role must be one of {sorted(VALID_ROLES)}")
    for field, value in data.items():
        setattr(u, field, value)
    db.commit()
    db.refresh(u)
    return UserItem.model_validate(u)
