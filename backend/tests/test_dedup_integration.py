import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.models import Case
from app.dedup.matcher import find_matching_case, normalize_name

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()

def test_find_matching_case_exact(db):
    c = Case(
        defendant_name="John Doe",
        defendant_name_normalized=normalize_name("John Doe"),
        sentencing_date=date(2026, 5, 19),
        state="TX",
    )
    db.add(c); db.commit()
    m = find_matching_case(db, "JOHN  DOE", date(2026, 5, 20), "TX")
    assert m is not None and m.id == c.id

def test_find_matching_case_outside_window_falls_back_to_name_and_state(db):
    """Same defendant + same state but dates far apart should still match
    (one article likely used a fallback date). Researcher can split via UI
    in the rare case they're actually different cases."""
    c = Case(
        defendant_name="John Doe",
        defendant_name_normalized=normalize_name("John Doe"),
        sentencing_date=date(2026, 5, 1),
        state="TX",
    )
    db.add(c); db.commit()
    m = find_matching_case(db, "John Doe", date(2026, 5, 20), "TX")
    assert m is not None and m.id == c.id


def test_find_matching_case_different_state_returns_none(db):
    """Same defendant name in a different state is treated as different."""
    c = Case(
        defendant_name="John Doe",
        defendant_name_normalized=normalize_name("John Doe"),
        sentencing_date=date(2026, 5, 1),
        state="TX",
    )
    db.add(c); db.commit()
    m = find_matching_case(db, "John Doe", date(2026, 5, 20), "CA")
    assert m is None
