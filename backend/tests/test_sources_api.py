from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.models import Source
from app.auth.dependencies import admin_required

client = TestClient(app)

# Bypass admin auth
app.dependency_overrides[admin_required] = lambda: MagicMock(
    id="00000000-0000-0000-0000-000000000001",
    email="admin@nbmediaproductions.com",
    role="admin",
)


def _make_source(db, name="newsapi", stype="news_api", is_active=True):
    s = Source(
        name=name,
        type=stype,
        config={},
        is_active=is_active,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def test_list_sources_returns_sources(db_session):
    _make_source(db_session, name="src-list-1")
    _make_source(db_session, name="src-list-2")
    r = client.get("/api/sources")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 2
    assert "items" in body


def test_toggle_source_deactivates(db_session):
    s = _make_source(db_session, name="src-toggle-1", is_active=True)
    r = client.patch(f"/api/sources/{s.id}", json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_toggle_source_404(db_session):
    r = client.patch(
        "/api/sources/00000000-0000-0000-0000-000000000099",
        json={"is_active": False},
    )
    assert r.status_code == 404


def test_run_source_queues_task(db_session):
    s = _make_source(db_session, name="src-run-1")
    with patch("app.api.sources.ingest_source.delay") as mock_delay:
        r = client.post(f"/api/sources/{s.id}/run")
    assert r.status_code == 200
    assert r.json()["queued"] is True
    mock_delay.assert_called_once_with(str(s.id))


def test_run_source_404(db_session):
    with patch("app.api.sources.ingest_source.delay"):
        r = client.post("/api/sources/00000000-0000-0000-0000-000000000099/run")
    assert r.status_code == 404
