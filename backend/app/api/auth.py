from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User
from app.auth.google_oauth import verify_id_token, EmailDomainNotAllowed
from app.auth.jwt_session import create_session_token
from app.schemas.auth import LoginRequest, LoginResponse, UserOut
from app.config import settings

router = APIRouter()

def _admin_emails() -> set[str]:
    return {e.strip().lower() for e in settings.admin_emails.split(",") if e.strip()}

@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    try:
        claims = verify_id_token(body.id_token)
    except EmailDomainNotAllowed as e:
        raise HTTPException(status_code=403, detail=str(e))

    user = db.query(User).filter(User.email == claims["email"]).one_or_none()
    role = "admin" if claims["email"] in _admin_emails() else "researcher"
    if user is None:
        user = User(
            email=claims["email"],
            google_sub=claims["google_sub"],
            full_name=claims["full_name"],
            role=role,
        )
        db.add(user)
    else:
        user.google_sub = claims["google_sub"]
        user.full_name = claims["full_name"] or user.full_name
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    token = create_session_token(user.id, user.email, user.role)
    response.set_cookie(
        "session", token,
        httponly=True, secure=settings.environment != "development",
        samesite="lax", max_age=7 * 24 * 3600,
    )
    return LoginResponse(user=UserOut.model_validate(user))

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("session")
    return {"ok": True}
