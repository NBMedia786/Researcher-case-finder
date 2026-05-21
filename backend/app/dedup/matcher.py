import re
import unicodedata
from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.models import Case

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")

def normalize_name(name: str) -> str:
    if not name:
        return ""
    # NFKD then strip combining marks to fold accents
    nfkd = unicodedata.normalize("NFKD", name)
    no_accent = "".join(c for c in nfkd if not unicodedata.combining(c))
    lowered = no_accent.lower()
    no_punct = _PUNCT_RE.sub("", lowered)
    return _WS_RE.sub(" ", no_punct).strip()

def find_matching_case(
    db: Session,
    defendant_name: str,
    sentencing_date: date,
    state: str,
    window_days: int = 3,
) -> Case | None:
    """Return existing case for the same defendant + state, else None.

    Strategy:
    1. First look within `window_days` of `sentencing_date` (the safe case
       — same defendant, dates close together, almost certainly same event).
    2. If no date-window match, fall back to (defendant_name + state) only.
       Same defendant in the same US state being sentenced for two
       different homicide cases is extremely rare in practice; the more
       common cause of date mismatch is one article reporting the original
       sentencing date and another using the article's publish date as a
       fallback. The researcher can split via the UI if a real duplicate
       collision happens.
    """
    if not defendant_name or not state:
        return None
    nname = normalize_name(defendant_name)
    if not nname:
        return None
    state_upper = state.upper()

    if sentencing_date is not None:
        lo = sentencing_date - timedelta(days=window_days)
        hi = sentencing_date + timedelta(days=window_days)
        match = (
            db.query(Case)
            .filter(Case.defendant_name_normalized == nname)
            .filter(Case.state == state_upper)
            .filter(Case.sentencing_date.between(lo, hi))
            .first()
        )
        if match is not None:
            return match

    # Fall back to defendant + state, no date constraint.
    return (
        db.query(Case)
        .filter(Case.defendant_name_normalized == nname)
        .filter(Case.state == state_upper)
        .first()
    )

def merge_extracted_into_case(case: Case, extracted: dict) -> None:
    """Fill empty fields on `case` with values from `extracted`. Never overwrite."""
    fillable = (
        "defendant_age", "defendant_hometown", "sentence_text", "sentence_years",
        "sentence_type", "court_name", "county", "docket_number", "judge_name",
        "prosecuting_office", "investigating_agency", "summary",
    )
    for f in fillable:
        if getattr(case, f, None) in (None, "", 0) and extracted.get(f):
            setattr(case, f, extracted[f])
