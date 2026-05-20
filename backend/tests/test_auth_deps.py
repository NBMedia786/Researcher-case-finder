from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from app.auth.dependencies import current_user, admin_required
from app.auth.jwt_session import create_session_token

app = FastAPI()

@app.get("/me")
def me(user=Depends(current_user)):
    return {"email": user.email, "role": user.role}

@app.get("/admin")
def admin(user=Depends(admin_required)):
    return {"ok": True}

client = TestClient(app)

def test_requires_session_cookie():
    r = client.get("/me")
    assert r.status_code == 401

def test_decodes_valid_session(monkeypatch):
    from unittest.mock import MagicMock
    fake_user = MagicMock(email="r@nbmediaproductions.com", role="researcher")
    monkeypatch.setattr(
        "app.auth.dependencies._load_user",
        lambda db, user_id: fake_user,
    )
    token = create_session_token("11111111-1111-1111-1111-111111111111",
                                 "r@nbmediaproductions.com", "researcher")
    client.cookies.set("session", token)
    r = client.get("/me")
    assert r.status_code == 200
    assert r.json()["email"] == "r@nbmediaproductions.com"
    client.cookies.clear()

def test_admin_required_rejects_researcher(monkeypatch):
    from unittest.mock import MagicMock
    fake_user = MagicMock(email="r@nbmediaproductions.com", role="researcher")
    monkeypatch.setattr(
        "app.auth.dependencies._load_user",
        lambda db, user_id: fake_user,
    )
    token = create_session_token("11111111-1111-1111-1111-111111111111",
                                 "r@nbmediaproductions.com", "researcher")
    client.cookies.set("session", token)
    r = client.get("/admin")
    assert r.status_code == 403
    client.cookies.clear()
