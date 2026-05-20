from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

VERIFIED = {
    "google_sub": "g-1",
    "email": "newuser@nbmediaproductions.com",
    "full_name": "New User",
}

def test_login_creates_user_and_returns_cookie(db_session):
    with patch("app.api.auth.verify_id_token", return_value=VERIFIED):
        r = client.post("/api/auth/login", json={"id_token": "x"})
    assert r.status_code == 200
    assert "session" in r.cookies
    assert r.json()["user"]["email"] == VERIFIED["email"]

def test_login_rejects_bad_domain():
    from app.auth.google_oauth import EmailDomainNotAllowed
    with patch("app.api.auth.verify_id_token", side_effect=EmailDomainNotAllowed("bad")):
        r = client.post("/api/auth/login", json={"id_token": "x"})
    assert r.status_code == 403
