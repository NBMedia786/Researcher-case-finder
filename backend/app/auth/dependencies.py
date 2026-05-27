import logging

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User
from app.auth.jwt_session import decode_session_token

_log = logging.getLogger(__name__)
_dev_bypass_logged = False


def _load_user(db: Session, user_id: str) -> User | None:
    return db.query(User).filter(User.id == user_id, User.is_active.is_(True)).one_or_none()


def _dev_bypass_user(db: Session) -> User | None:
    """Return the first active admin user. Used only when DEV_BYPASS_AUTH=true
    in the local .env — never on the VPS.
    """
    global _dev_bypass_logged
    if not _dev_bypass_logged:
        _log.warning(
            "DEV_BYPASS_AUTH is ENABLED — every request is treated as the "
            "first admin user. NEVER enable this on a public deployment."
        )
        _dev_bypass_logged = True
    return (
        db.query(User)
        .filter(User.role == "admin", User.is_active.is_(True))
        .order_by(User.email)
        .first()
    )


def current_user(
    session: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    if settings.dev_bypass_auth:
        user = _dev_bypass_user(db)
        if user is not None:
            return user
        # Fall through if no admin exists — surface a clear error rather
        # than silently failing.
        raise HTTPException(
            status_code=500,
            detail="DEV_BYPASS_AUTH set but no active admin user in DB",
        )

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
