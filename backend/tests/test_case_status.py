from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.models import Case
from app.dedup.matcher import normalize_name
from app.auth.dependencies import current_user
from unittest.mock import MagicMock

# Bypass auth for all tests in this module
app.dependency_overrides[current_user] = lambda: MagicMock(
    id="00000000-0000-0000-0000-000000000001",
    email="r@nbmediaproductions.com", role="researcher")

client = TestClient(app)


def _case(db, status="new"):
    c = Case(
        defendant_name="X Y",
        defendant_name_normalized=normalize_name("X Y"),
        sentencing_date=date(2026, 5, 19),
        state="TX", status=status, content_score=2,
    )
    db.add(c)
    db.commit()
    return c


def test_approve_transitions(db_session):
    c = _case(db_session)
    r = client.post(f"/api/cases/{c.id}/transition", json={"action": "approve"})
    assert r.status_code == 200
    db_session.refresh(c)
    assert c.status == "approved"


def test_reject_transitions(db_session):
    c = _case(db_session)
    r = client.post(f"/api/cases/{c.id}/transition", json={"action": "reject"})
    db_session.refresh(c)
    assert c.status == "rejected"


def test_invalid_action_rejected(db_session):
    c = _case(db_session)
    r = client.post(f"/api/cases/{c.id}/transition", json={"action": "nonsense"})
    assert r.status_code == 400
