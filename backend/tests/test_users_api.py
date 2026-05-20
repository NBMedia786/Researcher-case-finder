from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.models import User
from app.auth.dependencies import admin_required, current_user

client = TestClient(app)

# Bypass admin auth for admin endpoints
app.dependency_overrides[admin_required] = lambda: MagicMock(
    id="00000000-0000-0000-0000-000000000001",
    email="admin@nbmediaproductions.com",
    role="admin",
)


def _make_user(db, email, role="researcher", full_name="Test User"):
    u = User(email=email, role=role, full_name=full_name)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_list_users_returns_users(db_session):
    _make_user(db_session, email="user-list-1@example.com")
    _make_user(db_session, email="user-list-2@example.com")
    r = client.get("/api/users")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 2
    assert "items" in body


def test_update_user_role(db_session):
    u = _make_user(db_session, email="user-role@example.com", role="researcher")
    r = client.patch(f"/api/users/{u.id}", json={"role": "admin"})
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_update_user_invalid_role(db_session):
    u = _make_user(db_session, email="user-badrole@example.com")
    r = client.patch(f"/api/users/{u.id}", json={"role": "superuser"})
    assert r.status_code == 400


def test_update_user_404(db_session):
    r = client.patch(
        "/api/users/00000000-0000-0000-0000-000000000099",
        json={"full_name": "Nobody"},
    )
    assert r.status_code == 404


def test_update_user_deactivate(db_session):
    u = _make_user(db_session, email="user-deactivate@example.com")
    r = client.patch(f"/api/users/{u.id}", json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_me_returns_current_user(db_session):
    u = _make_user(db_session, email="me-user@example.com", role="researcher", full_name="Me User")
    # Override current_user to return this real user
    app.dependency_overrides[current_user] = lambda: u
    try:
        r = client.get("/api/auth/me")
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == "me-user@example.com"
        assert body["role"] == "researcher"
    finally:
        app.dependency_overrides.pop(current_user, None)


def test_me_unauthenticated():
    # Remove current_user override so real dependency runs (no cookie = 401)
    app.dependency_overrides.pop(current_user, None)
    try:
        r = client.get("/api/auth/me")
        assert r.status_code == 401
    finally:
        pass
