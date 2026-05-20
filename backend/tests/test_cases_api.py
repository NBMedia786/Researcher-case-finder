from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.models import Case
from app.dedup.matcher import normalize_name

client = TestClient(app)

# Bypass auth via dependency_overrides
from app.auth.dependencies import current_user
from unittest.mock import MagicMock

app.dependency_overrides[current_user] = lambda: MagicMock(
    id="00000000-0000-0000-0000-000000000001",
    email="r@nbmediaproductions.com", role="researcher")


def _make_case(db, **kw):
    c = Case(
        defendant_name=kw["name"],
        defendant_name_normalized=normalize_name(kw["name"]),
        sentencing_date=kw.get("d", date(2026, 5, 19)),
        state=kw.get("state", "TX"),
        status=kw.get("status", "new"),
        content_score=kw.get("score", 3),
    )
    db.add(c)
    db.commit()
    return c


def test_list_returns_new_cases(db_session):
    _make_case(db_session, name="John Doe")
    _make_case(db_session, name="Jane Roe")
    r = client.get("/api/cases?status=new")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 2
    assert all(i["status"] == "new" for i in body["items"])
