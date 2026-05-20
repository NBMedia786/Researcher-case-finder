from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User
from app.auth.jwt_session import decode_session_token

def _load_user(db: Session, user_id: str) -> User | None:
    return db.query(User).filter(User.id == user_id, User.is_active.is_(True)).one_or_none()

def current_user(
    session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not session:
        raise HTTPException(status_code=401, detail="not authenticated")
    try:
        claims = decode_session_token(session)
    except Exception:
        raise HTTPException(status_code=401, detail="invalid session")
    user = _load_user(db, claims["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="user not found")
    return user

def admin_required(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="admin required")
    return user
