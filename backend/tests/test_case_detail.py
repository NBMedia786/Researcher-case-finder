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


def test_case_detail_returns_full_record(db_session):
    c = Case(
        defendant_name="X Y",
        defendant_name_normalized=normalize_name("X Y"),
        sentencing_date=date(2026, 5, 19),
        state="TX", status="new", content_score=2,
    )
    db_session.add(c)
    db_session.commit()
    r = client.get(f"/api/cases/{c.id}")
    assert r.status_code == 200
    assert r.json()["defendant_name"] == "X Y"


def test_case_update_modifies_fields(db_session):
    c = Case(
        defendant_name="A B",
        defendant_name_normalized=normalize_name("A B"),
        sentencing_date=date(2026, 5, 19),
        state="TX", status="new", content_score=2,
    )
    db_session.add(c)
    db_session.commit()
    r = client.patch(f"/api/cases/{c.id}", json={"county": "Harris", "notes": "looks good"})
    assert r.status_code == 200
    db_session.refresh(c)
    assert c.county == "Harris"
    assert c.notes == "looks good"
